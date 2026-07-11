"""Scheduled tasks (v0.3): fire saved prompts as headless chat turns.

The lifespan starts `scheduler_loop()`, which ticks every minute while the
app runs. A due task's prompt goes through the SAME engine as a typed
message (`session_engine.process_message` — it needs no websocket; every
result persists to the DB), into a fresh session titled "⏰ …" and tagged in
`session_metadata`, so the run shows up in the sidebar like any other chat.

Safety comes free from the engine: anything send-side (email, invites) or a
skill deliverable pauses the session in `awaiting_review` and waits for a
human — a scheduled run can research and draft unattended, never send.

Missed runs (app closed at fire time): with `catch_up_missed` (the default,
Adam's call) the task fires ONCE on the next launch, marked late — the loop's
first tick runs immediately, which is what implements "run on reopen".
Without it the run is skipped and the task waits for its next slot. A run is
"late" once it's more than MISSED_GRACE past due, so ordinary tick jitter
never counts as a miss.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time as dtime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.core.default_user import get_default_user
from app.core.session_engine import AwaitingReviewEvent, process_message
from app.dependencies import SessionLocal, kv_store
from app.models import ScheduledTask, Session

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
MISSED_GRACE = timedelta(minutes=5)

# Task ids currently executing — guards the loop and Run-now against
# double-running the same task.
_running: set[UUID] = set()
# Strong refs to fire-and-forget Run-now tasks so they aren't GC'd mid-flight
# (same pattern as websocket.py's background sets).
_kicked: set[asyncio.Task] = set()


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.user_timezone)
    except Exception:  # noqa: BLE001 — a bad tz string must never kill the loop
        return ZoneInfo("UTC")


def is_running(task_id: UUID) -> bool:
    return task_id in _running


def compute_next_run(schedule: dict, after: datetime) -> datetime:
    """Next fire time (aware UTC) strictly after `after`, evaluated in the
    user's local timezone so "daily at 09:00" means 09:00 on their wall
    clock."""
    tz = _tz()
    local_after = after.astimezone(tz)
    kind = schedule.get("kind", "daily")

    if kind == "every_n_hours":
        n = min(24, max(1, int(schedule.get("every_hours", 6))))
        # Deterministic anchors from local midnight (00:00, 06:00, 12:00, …
        # for n=6) rather than "n hours from whenever the app happened to
        # boot" — predictable for the user, stable across restarts.
        for day_offset in (0, 1):
            base = datetime.combine(
                local_after.date() + timedelta(days=day_offset), dtime(0, 0), tzinfo=tz
            )
            for k in range(0, (24 // n) + 1):
                candidate = base + timedelta(hours=k * n)
                if candidate > local_after:
                    return candidate.astimezone(timezone.utc)
        return (local_after + timedelta(hours=n)).astimezone(timezone.utc)

    hh, mm = (int(part) for part in str(schedule.get("time", "09:00")).split(":", 1))
    fire_time = dtime(hh, mm)
    if kind == "weekdays":
        allowed = (0, 1, 2, 3, 4)
    elif kind == "weekly":
        allowed = (min(6, max(0, int(schedule.get("weekday", 0)))),)
    else:  # daily
        allowed = (0, 1, 2, 3, 4, 5, 6)
    for day_offset in range(0, 8):
        day = local_after.date() + timedelta(days=day_offset)
        candidate = datetime.combine(day, fire_time, tzinfo=tz)
        if day.weekday() in allowed and candidate > local_after:
            return candidate.astimezone(timezone.utc)
    # Unreachable (8 days always contains an allowed weekday), but stay sane.
    return (local_after + timedelta(days=1)).astimezone(timezone.utc)


async def run_task_now(task_id: UUID, *, catch_up: bool = False) -> None:
    """Execute one run of a task, headlessly, in its own DB session. Used by
    both the tick loop and the Run-now endpoint."""
    if task_id in _running:
        logger.info("scheduler: task %s already running — skipped", task_id)
        return
    _running.add(task_id)
    try:
        async with SessionLocal() as db:
            task = await db.get(ScheduledTask, task_id)
            if task is None:
                return
            now = datetime.now(timezone.utc)
            user = await get_default_user(db)
            chat = Session(
                id=uuid4(),
                user_id=user.id,
                project_id=task.project_id,
                title=f"⏰ {task.name}",
                session_metadata={
                    "source": "scheduled_task",
                    "task_id": str(task.id),
                    "late": catch_up,
                },
            )
            db.add(chat)
            await db.commit()

            status = "ok"
            try:
                async for event in process_message(
                    db=db, kv=kv_store, session_id=chat.id, user_text=task.prompt
                ):
                    if isinstance(event, AwaitingReviewEvent):
                        # Deliverable or send-side action staged — it waits for
                        # a human in the session, exactly like an interactive
                        # turn. Surface that in the task's status.
                        status = "awaiting your review"
            except Exception as e:  # noqa: BLE001 — a failed run must not kill the loop
                logger.exception("scheduler: run of task %s failed", task_id)
                status = f"error: {type(e).__name__}: {e}"[:480]

            task.last_run_at = now
            task.last_status = f"ran late (missed while closed) — {status}" if catch_up else status
            task.last_session_id = chat.id
            task.next_run_at = compute_next_run(task.schedule, datetime.now(timezone.utc))
            await db.commit()
            logger.info("scheduler: task %s (%s) finished: %s", task.name, task_id, status)
    finally:
        _running.discard(task_id)


def kick_run(task_id: UUID) -> None:
    """Fire-and-forget a run (the Run-now endpoint)."""
    task = asyncio.create_task(run_task_now(task_id))
    _kicked.add(task)
    task.add_done_callback(_kicked.discard)


async def tick(now: datetime | None = None) -> int:
    """One scheduler pass: decide skip-vs-run for every due task, then run
    sequentially (one model call at a time). Returns how many ran."""
    now = now or datetime.now(timezone.utc)
    plans: list[tuple[UUID, bool]] = []
    async with SessionLocal() as db:
        due = (
            await db.scalars(
                select(ScheduledTask).where(
                    ScheduledTask.enabled.is_(True),
                    ScheduledTask.next_run_at.is_not(None),
                    ScheduledTask.next_run_at <= now,
                )
            )
        ).all()
        for task in due:
            late = (now - task.next_run_at) > MISSED_GRACE
            if late and not task.catch_up_missed:
                task.last_status = "skipped — missed while Momentum was closed"
                task.next_run_at = compute_next_run(task.schedule, now)
            else:
                plans.append((task.id, late))
        await db.commit()

    ran = 0
    for task_id, late in plans:
        await run_task_now(task_id, catch_up=late)
        ran += 1
    return ran


async def scheduler_loop() -> None:
    """Started by the app lifespan; cancelled on shutdown. Ticks immediately
    (catch-up-on-launch), then every TICK_SECONDS."""
    logger.info("scheduler: loop started (tick every %ss)", TICK_SECONDS)
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — the loop must survive any tick failure
            logger.exception("scheduler: tick failed")
        await asyncio.sleep(TICK_SECONDS)
