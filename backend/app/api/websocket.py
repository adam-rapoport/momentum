"""WebSocket endpoint that drives the conversation loop.

Inbound:
  { "type": "session.message", "session_id": "...", "content": "..." }
  { "type": "session.cancel",  "session_id": "..." }

Outbound:
  { "type": "stream.text",  "session_id": "...", "text": "..." }
  { "type": "stream.done",  "session_id": "...", "usage": {...}, "metadata": {...} }
  { "type": "error", "code": "...", "message": "...", "session_id"?: "..." }
"""
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import APIError as OpenAIAPIError
from pydantic import ValidationError

from app.core.session_engine import (
    AwaitingReviewEvent,
    CommitFailedError,
    DoneEvent,
    TextEvent,
    ToolResultEvent,
    ToolStartEvent,
    cancel_session,
    process_message,
)
from app.dependencies import SessionLocal, redis_client
from app.schemas.websocket import InboundCancel, InboundMessage

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


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type")

            if msg_type == "session.message":
                try:
                    payload = InboundMessage.model_validate(raw)
                except ValidationError as e:
                    await ws.send_json({"type": "error", "code": "VALIDATION_ERROR", "message": str(e)})
                    continue
                await _handle_user_message(ws, payload.session_id, payload.content)

            elif msg_type == "session.cancel":
                try:
                    payload_c = InboundCancel.model_validate(raw)
                except ValidationError as e:
                    await ws.send_json({"type": "error", "code": "VALIDATION_ERROR", "message": str(e)})
                    continue
                await cancel_session(redis_client, payload_c.session_id)

            else:
                await ws.send_json(
                    {"type": "error", "code": "UNKNOWN_MESSAGE_TYPE", "message": f"unknown type: {msg_type}"}
                )
    except WebSocketDisconnect:
        return


async def _handle_user_message(ws: WebSocket, session_id: UUID, content: str) -> None:
    try:
        async with SessionLocal() as db:
            async for event in process_message(
                db=db, redis=redis_client, session_id=session_id, user_text=content
            ):
                if isinstance(event, TextEvent):
                    await ws.send_json(
                        {"type": "stream.text", "session_id": str(session_id), "text": event.text}
                    )
                elif isinstance(event, ToolStartEvent):
                    await ws.send_json(
                        {
                            "type": "stream.tool_start",
                            "session_id": str(session_id),
                            "call_id": event.call_id,
                            "name": event.name,
                            "input": event.input,
                        }
                    )
                elif isinstance(event, ToolResultEvent):
                    await ws.send_json(
                        {
                            "type": "stream.tool_result",
                            "session_id": str(session_id),
                            "call_id": event.call_id,
                            "name": event.name,
                            "output": event.output,
                            "is_error": event.is_error,
                        }
                    )
                elif isinstance(event, AwaitingReviewEvent):
                    await ws.send_json(
                        {
                            "type": "stream.awaiting_review",
                            "session_id": str(session_id),
                            "deliverable_kind": event.deliverable_kind,
                            "document_id": event.document_id,
                            "summary_for_user": event.summary_for_user,
                            "url": event.url,
                            "model": event.model,
                        }
                    )
                elif isinstance(event, DoneEvent):
                    await ws.send_json(
                        {
                            "type": "stream.done",
                            "session_id": str(session_id),
                            "usage": {
                                "input_tokens": event.input_tokens,
                                "output_tokens": event.output_tokens,
                                "cost_usd": str(event.cost_usd),
                                "total_cost_usd": str(event.total_cost_usd),
                            },
                            "metadata": {"cancelled": event.cancelled, "model": event.model},
                        }
                    )
    except WebSocketDisconnect:
        # The client hung up while we were mid-stream. `async with SessionLocal()`
        # will roll back any uncommitted work on exit. Let the outer handler
        # see the disconnect so it can exit the read loop cleanly.
        logger.info("client disconnected mid-stream for session %s", session_id)
        raise
    except ValueError as e:
        await ws.send_json(
            {"type": "error", "code": "NOT_FOUND", "message": str(e), "session_id": str(session_id)}
        )
    except CommitFailedError as e:
        # DB write failed partway through the turn. The session engine has
        # already rolled back; tell the user the turn didn't save so they
        # know their message may need to be re-sent.
        logger.warning(
            "commit failure at stage=%s for session %s", e.stage, session_id
        )
        await ws.send_json(
            {
                "type": "error",
                "code": "DB_ERROR",
                "message": (
                    "Couldn't save this turn to the database — the partial "
                    "state has been rolled back. Please try again; if this "
                    "keeps happening, check the backend logs."
                ),
                "session_id": str(session_id),
            }
        )
    except OpenAIAPIError as e:
        # Groq rejected the model's output — almost always because the model
        # emitted malformed tool_calls on this sampling. Recoverable: tell
        # the user to retry, don't scare them with a stack trace.
        msg = str(e).lower()
        is_tool_failure = any(hint in msg for hint in _TOOL_CALL_FAILURE_HINTS)
        logger.warning("LLM API error for session %s: %s", session_id, e)
        if is_tool_failure:
            await ws.send_json(
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
                }
            )
        else:
            await ws.send_json(
                {
                    "type": "error",
                    "code": "MODEL_API_ERROR",
                    "message": (
                        f"The model service returned an error: {e}. "
                        "Try again in a moment."
                    ),
                    "session_id": str(session_id),
                }
            )
    except Exception:
        logger.exception("error processing message for session %s", session_id)
        await ws.send_json(
            {
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong processing your message.",
                "session_id": str(session_id),
            }
        )
