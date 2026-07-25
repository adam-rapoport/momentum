"""Scheduled tasks (v0.3): next-run math, tick catch-up/skip semantics,
headless execution, and the CRUD/run-now endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core import scheduler
from app.core.scheduler import MISSED_GRACE, compute_next_run, run_task_now, tick
from app.core.seed import ensure_default_setup
from app.core.session_engine import DoneEvent, TextEvent
from app.models import ScheduledTask, Session

LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture(autouse=True)
def _fixed_tz(monkeypatch):
    monkeypatch.setattr(settings, "user_timezone", "America/Los_Angeles")


@pytest.fixture
async def loop_local_sessions(test_engine, monkeypatch):
    """Bind the scheduler's own DB sessions to this test's engine.

    run_task_now/tick open sessions via the app-global SessionLocal, whose
    engine pools asyncpg connections across event loops — so on Postgres a
    connection pooled by one test resurfaces in the next test's loop and
    dies with "attached to a different loop". The function-scoped NullPool
    test_engine keeps every connection on the current test's loop.
    """
    monkeypatch.setattr(
        scheduler,
        "SessionLocal",
        async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession),
    )


def _la(y, m, d, hh, mm) -> datetime:
    """Aware UTC instant for a Los Angeles wall-clock time."""
    return datetime(y, m, d, hh, mm, tzinfo=LA).astimezone(timezone.utc)


# ── compute_next_run (pure) ────────────────────────────────────────────────
# 2026-07-10 is a Friday.


def test_daily_before_and_after_fire_time():
    sched = {"kind": "daily", "time": "09:00"}
    assert compute_next_run(sched, _la(2026, 7, 10, 8, 0)) == _la(2026, 7, 10, 9, 0)
    assert compute_next_run(sched, _la(2026, 7, 10, 10, 0)) == _la(2026, 7, 11, 9, 0)
    # strictly after: exactly at fire time rolls to the next day
    assert compute_next_run(sched, _la(2026, 7, 10, 9, 0)) == _la(2026, 7, 11, 9, 0)


def test_weekdays_skip_the_weekend():
    sched = {"kind": "weekdays", "time": "09:00"}
    # Friday after 09:00 → Monday 09:00
    assert compute_next_run(sched, _la(2026, 7, 10, 10, 0)) == _la(2026, 7, 13, 9, 0)


def test_weekly_wraps_to_next_week():
    sched = {"kind": "weekly", "time": "14:30", "weekday": 2}  # Wednesday
    # Thursday → the following Wednesday
    assert compute_next_run(sched, _la(2026, 7, 9, 9, 0)) == _la(2026, 7, 15, 14, 30)


def test_every_n_hours_anchors_to_local_midnight():
    sched = {"kind": "every_n_hours", "every_hours": 6}
    assert compute_next_run(sched, _la(2026, 7, 10, 7, 0)) == _la(2026, 7, 10, 12, 0)
    assert compute_next_run(sched, _la(2026, 7, 10, 23, 30)) == _la(2026, 7, 11, 0, 0)


def test_next_run_is_utc_aware():
    got = compute_next_run({"kind": "daily", "time": "09:00"}, datetime.now(timezone.utc))
    assert got.tzinfo is timezone.utc


# ── headless execution + tick (real test DB) ───────────────────────────────


async def _default_ids(db):
    await ensure_default_setup(db)
    from app.core.default_user import get_default_project, get_default_user

    user = await get_default_user(db)
    project = await get_default_project(db, user.organization_id)
    return user, project


def _make_task(project_id, **overrides) -> ScheduledTask:
    fields = dict(
        id=uuid4(),
        project_id=project_id,
        name="Morning brief",
        prompt="Summarize what changed yesterday.",
        schedule={"kind": "daily", "time": "09:00"},
        enabled=True,
        catch_up_missed=True,
        next_run_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return ScheduledTask(**fields)


def _stub_engine(events):
    async def fake_process_message(*, db, kv, session_id, user_text, attachment_ids=None):
        for event in events:
            yield event

    return fake_process_message


async def test_run_task_now_persists_a_tagged_session(db, monkeypatch, loop_local_sessions):
    _user, project = await _default_ids(db)
    task = _make_task(project.id)
    task_id = task.id
    db.add(task)
    await db.commit()

    done = DoneEvent(
        input_tokens=1,
        output_tokens=1,
        cost_usd=Decimal("0"),
        total_cost_usd=Decimal("0"),
        cancelled=False,
    )
    monkeypatch.setattr(scheduler, "process_message", _stub_engine([TextEvent("hi"), done]))

    await run_task_now(task_id)

    db.expire_all()
    fresh = await db.get(ScheduledTask, task_id)
    assert fresh.last_status == "ok"
    assert fresh.last_run_at is not None
    assert fresh.next_run_at > datetime.now(timezone.utc)
    chat = await db.get(Session, fresh.last_session_id)
    assert chat is not None
    assert chat.title.startswith("⏰")
    assert chat.session_metadata["source"] == "scheduled_task"
    assert chat.session_metadata["task_id"] == str(task_id)


async def test_run_task_now_records_engine_failure(db, monkeypatch, loop_local_sessions):
    _user, project = await _default_ids(db)
    task = _make_task(project.id)
    task_id = task.id
    db.add(task)
    await db.commit()

    async def boom(**kwargs):
        raise RuntimeError("no provider key configured")
        yield  # pragma: no cover — makes this an async generator

    monkeypatch.setattr(scheduler, "process_message", boom)

    await run_task_now(task_id)

    db.expire_all()
    fresh = await db.get(ScheduledTask, task_id)
    assert fresh.last_status.startswith("error: RuntimeError")
    # the run still reschedules — one failure must not stall the recurrence
    assert fresh.next_run_at > datetime.now(timezone.utc)


async def test_tick_skips_long_missed_run_when_catch_up_off(db, monkeypatch, loop_local_sessions):
    _user, project = await _default_ids(db)
    task = _make_task(
        project.id,
        catch_up_missed=False,
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    task_id = task.id
    db.add(task)
    await db.commit()

    called = []

    async def fake_run(task_id, *, catch_up=False):
        called.append((task_id, catch_up))

    monkeypatch.setattr(scheduler, "run_task_now", fake_run)

    ran = await tick()

    assert ran == 0 and called == []
    db.expire_all()
    fresh = await db.get(ScheduledTask, task_id)
    assert fresh.last_status.startswith("skipped")
    assert fresh.next_run_at > datetime.now(timezone.utc)


async def test_tick_catches_up_missed_run_by_default(db, monkeypatch, loop_local_sessions):
    _user, project = await _default_ids(db)
    task = _make_task(
        project.id,
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    task_id = task.id
    db.add(task)
    await db.commit()

    called = []

    async def fake_run(task_id, *, catch_up=False):
        called.append((task_id, catch_up))

    monkeypatch.setattr(scheduler, "run_task_now", fake_run)

    ran = await tick()

    assert ran == 1
    assert called == [(task_id, True)]  # marked late


async def test_tick_runs_freshly_due_task_within_grace(db, monkeypatch, loop_local_sessions):
    """A run that came due seconds ago is normal tick jitter, not a miss —
    it runs even with catch-up off."""
    _user, project = await _default_ids(db)
    task = _make_task(
        project.id,
        catch_up_missed=False,
        next_run_at=datetime.now(timezone.utc) - (MISSED_GRACE / 2),
    )
    task_id = task.id
    db.add(task)
    await db.commit()

    called = []

    async def fake_run(task_id, *, catch_up=False):
        called.append((task_id, catch_up))

    monkeypatch.setattr(scheduler, "run_task_now", fake_run)

    ran = await tick()

    assert ran == 1
    assert called == [(task_id, False)]


async def test_tick_ignores_disabled_tasks(db, monkeypatch, loop_local_sessions):
    _user, project = await _default_ids(db)
    task = _make_task(project.id, enabled=False)
    db.add(task)
    await db.commit()

    async def fake_run(task_id, *, catch_up=False):  # pragma: no cover
        raise AssertionError("disabled task must not run")

    monkeypatch.setattr(scheduler, "run_task_now", fake_run)
    assert await tick() == 0


# ── endpoints (real app via the client fixture) ────────────────────────────

API = "/api/v1/scheduled-tasks"


def test_scheduled_task_crud_roundtrip(client):
    r = client.post(
        API,
        json={
            "name": "Weekly digest",
            "prompt": "Draft my weekly stakeholder digest.",
            "schedule": {"kind": "weekly", "time": "08:30", "weekday": 0},
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["next_run_at"] is not None
    assert body["catch_up_missed"] is True
    task_id = body["id"]

    assert [t["id"] for t in client.get(API).json()] == [task_id]

    r = client.put(f"{API}/{task_id}", json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    # re-enabling recomputes the fire time instead of reviving a stale one
    r = client.put(f"{API}/{task_id}", json={"enabled": True})
    assert r.json()["enabled"] is True and r.json()["next_run_at"] is not None

    assert client.delete(f"{API}/{task_id}").status_code == 204
    assert client.get(API).json() == []


def test_invalid_schedule_is_rejected(client):
    r = client.post(
        API,
        json={"name": "x", "prompt": "p", "schedule": {"kind": "daily", "time": "25:99"}},
    )
    assert r.status_code == 422


def test_run_now_kicks_a_run(client, monkeypatch):
    ran = []

    async def fake_run(task_id, *, catch_up=False):
        ran.append(task_id)

    monkeypatch.setattr("app.core.scheduler.run_task_now", fake_run)

    r = client.post(
        API,
        json={
            "name": "One-off",
            "prompt": "p",
            "schedule": {"kind": "daily", "time": "09:00"},
        },
    )
    task_id = r.json()["id"]
    r = client.post(f"{API}/{task_id}/run-now")
    assert r.status_code == 200
    assert r.json() == {"status": "started"}


def test_run_now_missing_task_404(client):
    from uuid import uuid4 as u

    assert client.post(f"{API}/{u()}/run-now").status_code == 404
