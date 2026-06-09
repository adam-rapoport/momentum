"""WebSocket endpoint that drives the conversation loop.

Inbound:
  { "type": "session.message", "session_id": "...", "content": "..." }
  { "type": "session.cancel",  "session_id": "..." }

Outbound:
  { "type": "stream.text",  "session_id": "...", "text": "..." }
  { "type": "stream.done",  "session_id": "...", "usage": {...}, "metadata": {...} }
  { "type": "error", "code": "...", "message": "...", "session_id"?: "..." }

Concurrency model (Phase 1, finding A1): a turn runs as an asyncio.Task so
the read loop keeps receiving while the model streams — that's what lets a
`session.cancel` frame actually arrive mid-turn. One in-flight turn per
session, process-wide; a second `session.message` for a busy session is
rejected with TURN_IN_PROGRESS instead of queueing.
"""
import asyncio
import logging
from uuid import UUID
from weakref import WeakKeyDictionary

import sentry_sdk
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import APIError as OpenAIAPIError
from pydantic import ValidationError
from starlette.websockets import WebSocketState

from app.core.session_engine import (
    ApprovalPendingError,
    AwaitingReviewEvent,
    CommitFailedError,
    DoneEvent,
    TextEvent,
    ToolResultEvent,
    ToolStartEvent,
    cancel_session,
    process_message,
)
from app.dependencies import SessionLocal, kv_store
from app.schemas.websocket import InboundCancel, InboundMessage
from app.security import origin_allowed, token_valid

logger = logging.getLogger(__name__)

# Substrings in a provider APIError message that mean "the model emitted
# malformed tool calls" (as opposed to a network / auth / rate-limit issue).
# Groq surfaces these as tool_use_failed; Google surfaces them differently
# (e.g. thought_signature complaints) and those tend NOT to be
# retry-recoverable, so we leave those out of this list on purpose.
_TOOL_CALL_FAILURE_HINTS = (
    "failed to call a function",
    "tool_use_failed",
)

router = APIRouter()

# One in-flight turn task per session, process-wide. Keyed by session_id so a
# second `session.message` for a busy session (even from another connection)
# is rejected instead of interleaving two turns (findings A1/A3). Entries are
# removed by each task's done-callback.
_turn_tasks: dict[UUID, asyncio.Task] = {}

# Per-connection send serialization: two concurrent turn tasks (different
# sessions, same socket) must not interleave their ASGI send calls.
_send_locks: "WeakKeyDictionary[WebSocket, asyncio.Lock]" = WeakKeyDictionary()


async def _send(ws: WebSocket, payload: dict) -> bool:
    """Send a JSON frame, guarding against a socket that closed mid-turn.
    Returns False (instead of raising) when the client is gone — turn tasks
    use that to stop streaming; the read loop's cleanup cancels them anyway.
    """
    if getattr(ws, "client_state", WebSocketState.CONNECTED) != WebSocketState.CONNECTED:
        return False
    lock = _send_locks.get(ws)
    if lock is None:
        lock = _send_locks.setdefault(ws, asyncio.Lock())
    try:
        async with lock:
            await ws.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError is starlette's "Cannot call send once a close message
        # has been sent" — the disconnect raced our send.
        return False


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    # WebSockets are NOT subject to CORS: without this check any website the
    # user visits could open ws://127.0.0.1:8000/ws and drive the agent (send
    # email, read memory). Browser WS clients can't set headers, so the
    # desktop shell's per-launch token arrives as a query param instead.
    # See app.security for the threat model.
    if not origin_allowed(ws.headers.get("origin")) or not token_valid(
        ws.query_params.get("token")
    ):
        await ws.close(code=1008)  # policy violation
        return
    await ws.accept()
    # Turn tasks spawned by THIS connection — cancelled when it goes away so
    # their finally blocks (engine contextvar/cancel-key cleanup, DB rollback)
    # run promptly instead of streaming into a dead socket.
    own_tasks: set[asyncio.Task] = set()
    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type")

            if msg_type == "session.message":
                try:
                    payload = InboundMessage.model_validate(raw)
                except ValidationError as e:
                    await _send(ws, {"type": "error", "code": "VALIDATION_ERROR", "message": str(e)})
                    continue
                existing = _turn_tasks.get(payload.session_id)
                if existing is not None and not existing.done():
                    await _send(
                        ws,
                        {
                            "type": "error",
                            "code": "TURN_IN_PROGRESS",
                            "message": (
                                "A response is already being generated for this "
                                "session. Wait for it to finish or stop it first."
                            ),
                            "session_id": str(payload.session_id),
                        },
                    )
                    continue
                task = asyncio.create_task(
                    _handle_user_message(ws, payload.session_id, payload.content),
                    name=f"turn-{payload.session_id}",
                )
                _turn_tasks[payload.session_id] = task
                own_tasks.add(task)
                task.add_done_callback(
                    _turn_task_cleanup(payload.session_id, own_tasks)
                )

            elif msg_type == "session.cancel":
                try:
                    payload_c = InboundCancel.model_validate(raw)
                except ValidationError as e:
                    await _send(ws, {"type": "error", "code": "VALIDATION_ERROR", "message": str(e)})
                    continue
                # Just set the KV flag — the engine checks it on every chunk,
                # at the top of each tool-loop iteration, and before each tool
                # execution, then winds the turn down cleanly (persisting the
                # partial text) and emits stream.done with cancelled=true.
                await cancel_session(kv_store, payload_c.session_id)

            else:
                await _send(
                    ws,
                    {"type": "error", "code": "UNKNOWN_MESSAGE_TYPE", "message": f"unknown type: {msg_type}"},
                )
    except WebSocketDisconnect:
        return
    finally:
        for task in own_tasks:
            task.cancel()


def _turn_task_cleanup(session_id: UUID, own_tasks: set[asyncio.Task]):
    def _cleanup(task: asyncio.Task) -> None:
        if _turn_tasks.get(session_id) is task:
            _turn_tasks.pop(session_id, None)
        own_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()  # also marks the exception as retrieved
        if exc is not None:
            # _handle_user_message catches everything it can answer for; a
            # leak here means the socket died before we could even report.
            logger.warning(
                "turn task for session %s died unreported: %r", session_id, exc
            )

    return _cleanup


def _event_frame(event, session_id: UUID) -> dict | None:
    """Engine event -> outbound JSON frame. These shapes are the frontend
    contract (pinned in tests/integration/test_ws_contract.py) — fields may
    be added but never removed or renamed."""
    sid = str(session_id)
    if isinstance(event, TextEvent):
        return {"type": "stream.text", "session_id": sid, "text": event.text}
    if isinstance(event, ToolStartEvent):
        return {
            "type": "stream.tool_start",
            "session_id": sid,
            "call_id": event.call_id,
            "name": event.name,
            "input": event.input,
        }
    if isinstance(event, ToolResultEvent):
        return {
            "type": "stream.tool_result",
            "session_id": sid,
            "call_id": event.call_id,
            "name": event.name,
            "output": event.output,
            "is_error": event.is_error,
        }
    if isinstance(event, AwaitingReviewEvent):
        return {
            "type": "stream.awaiting_review",
            "session_id": sid,
            "kind": event.kind,
            "deliverable_kind": event.deliverable_kind,
            "document_id": event.document_id,
            "summary_for_user": event.summary_for_user,
            "url": event.url,
            "model": event.model,
            "pending_action": event.pending_action,
        }
    if isinstance(event, DoneEvent):
        return {
            "type": "stream.done",
            "session_id": sid,
            "usage": {
                "input_tokens": event.input_tokens,
                "output_tokens": event.output_tokens,
                "cost_usd": str(event.cost_usd),
                "total_cost_usd": str(event.total_cost_usd),
            },
            "metadata": {"cancelled": event.cancelled, "model": event.model},
        }
    return None


async def _handle_user_message(ws: WebSocket, session_id: UUID, content: str) -> None:
    try:
        async with SessionLocal() as db:
            agen = process_message(
                db=db, kv=kv_store, session_id=session_id, user_text=content
            )
            try:
                async for event in agen:
                    frame = _event_frame(event, session_id)
                    if frame is None:
                        continue
                    if not await _send(ws, frame):
                        # Client hung up mid-stream. Stop consuming; aclose()
                        # below runs the engine's finally cleanup and the
                        # `async with SessionLocal()` exit rolls back any
                        # uncommitted work.
                        logger.info(
                            "client disconnected mid-stream for session %s",
                            session_id,
                        )
                        break
            finally:
                await agen.aclose()
    except asyncio.CancelledError:
        # Connection went away and the read loop cancelled us — the finally
        # above already closed the engine generator. Re-raise so the task is
        # marked cancelled, not failed.
        raise
    except ValueError as e:
        await _send(
            ws,
            {"type": "error", "code": "NOT_FOUND", "message": str(e), "session_id": str(session_id)},
        )
    except ApprovalPendingError as e:
        # The session is paused on a staged side effect (send email / create
        # event) and the reply wasn't approve/revise/restart. We refuse to run
        # a model turn that could fire side effects (finding A6) — the user
        # must use the approval buttons.
        await _send(
            ws,
            {
                "type": "error",
                "code": "APPROVAL_REQUIRED",
                "message": str(e),
                "session_id": str(session_id),
            },
        )
    except CommitFailedError as e:
        # DB write failed partway through the turn. The session engine has
        # already rolled back; tell the user the turn didn't save so they
        # know their message may need to be re-sent.
        logger.warning(
            "commit failure at stage=%s for session %s", e.stage, session_id
        )
        # Genuine failure (not user-recoverable) — report it. No-op if Sentry
        # isn't configured.
        sentry_sdk.capture_exception(e)
        await _send(
            ws,
            {
                "type": "error",
                "code": "DB_ERROR",
                "message": (
                    "Couldn't save this turn to the database — the partial "
                    "state has been rolled back. Please try again; if this "
                    "keeps happening, check the backend logs."
                ),
                "session_id": str(session_id),
            },
        )
    except OpenAIAPIError as e:
        # Groq rejected the model's output — almost always because the model
        # emitted malformed tool_calls on this sampling. Recoverable: tell
        # the user to retry, don't scare them with a stack trace.
        msg = str(e).lower()
        is_tool_failure = any(hint in msg for hint in _TOOL_CALL_FAILURE_HINTS)
        logger.warning("LLM API error for session %s: %s", session_id, e)
        if is_tool_failure:
            await _send(
                ws,
                {
                    "type": "error",
                    "code": "MODEL_TOOL_CALL_FAILED",
                    "message": (
                        "The model produced a malformed tool call and the LLM "
                        "provider rejected the response. This happens occasionally, "
                        "especially during long skill workflows. Please retry "
                        "your last message — it usually works on the second try."
                    ),
                    "session_id": str(session_id),
                },
            )
        else:
            await _send(
                ws,
                {
                    "type": "error",
                    "code": "MODEL_API_ERROR",
                    "message": (
                        f"The model service returned an error: {e}. "
                        "Try again in a moment."
                    ),
                    "session_id": str(session_id),
                },
            )
    except Exception as e:
        logger.exception("error processing message for session %s", session_id)
        # Unexpected crash — report it. No-op if Sentry isn't configured.
        sentry_sdk.capture_exception(e)
        await _send(
            ws,
            {
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong processing your message.",
                "session_id": str(session_id),
            },
        )
