"""The conversation loop. Takes a user's message, runs it through Groq with
tools available, streams text + tool events back, persists every message.

Sprint 2 scope: tools + streaming tool events. System prompt is still a
placeholder — the real PM prompt lands in Chunk 5 of Sprint 2.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.documents import router as docs_router
from app.core.groq_client import StreamChunk, StreamResult
from app.core.llm import stream_message
from app.core.model_router import select_model
from app.core.pending_actions import (
    clear_pending_action,
    execute_pending_action,
    get_pending_action,
)
from app.core.skills import CLEAR_SENTINEL, detect_skill, get_skill
from app.core.system_prompt import build_prompt
from app.core.tools import (
    ToolContext,
    _load_builtin_tools,
    all_tools,
    execute_tool,
    reset_context,
    set_context,
    to_openai_tools,
)
from app.models import Message, Session

logger = logging.getLogger(__name__)

# Import tool modules so their `register(...)` calls run once at process start.
_load_builtin_tools()

MAX_TOOL_ITERATIONS = 8


def _split_concatenated_json_args(raw: str) -> list[dict] | None:
    """Split a string that contains multiple concatenated JSON objects.

    Gemini via the Google OpenAI-compat shim occasionally merges N parallel
    tool calls into a single tool_call with arguments that are just
    `{"a":1}{"b":2}{"c":3}` — not valid JSON on its own, but parseable as a
    sequence of objects. We salvage those so the tool still runs.

    Returns None when the input is valid JSON on its own (no salvage needed)
    or when we can't make sense of it as a clean object sequence. Returns a
    list of dicts when we detect >=2 concatenated objects.
    """
    s = (raw or "").strip()
    if not s:
        return None

    try:
        json.loads(s)
        return None  # already valid — don't touch it
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    results: list[dict] = []
    idx = 0
    try:
        while idx < len(s):
            obj, offset = decoder.raw_decode(s, idx)
            if not isinstance(obj, dict):
                return None
            results.append(obj)
            idx = offset
            while idx < len(s) and s[idx] in " \t\n\r,":
                idx += 1
    except json.JSONDecodeError:
        return None

    return results if len(results) >= 2 else None


class CommitFailedError(RuntimeError):
    """Raised when a turn-scoped DB commit fails. Carries the stage label so
    the websocket layer can report where the turn broke (persisting the user
    message, the assistant message, a tool result, etc.) without leaking the
    raw SQLAlchemy error text to the user.
    """

    def __init__(self, stage: str, original: BaseException) -> None:
        super().__init__(f"commit failed during {stage}: {original}")
        self.stage = stage
        self.original = original


async def _safe_commit(db: AsyncSession, session_id: UUID, stage: str) -> None:
    """Commit the current transaction. On failure, roll back and raise
    CommitFailedError — callers upstack treat this as a session-fatal error
    and surface it via a WS `DB_ERROR` event.
    """
    try:
        await db.commit()
    except Exception as e:  # noqa: BLE001 — rewrap and propagate
        logger.exception(
            "db commit failed at %s for session %s", stage, session_id
        )
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001 — rollback errors are best-effort
            logger.exception("rollback also failed for session %s", session_id)
        raise CommitFailedError(stage, e) from e


def _cancel_key(session_id: UUID) -> str:
    return f"session:{session_id}:cancel"


@dataclass
class TextEvent:
    text: str


@dataclass
class ToolStartEvent:
    call_id: str
    name: str
    input: dict


@dataclass
class ToolResultEvent:
    call_id: str
    name: str
    output: str
    is_error: bool = False


@dataclass
class DoneEvent:
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    total_cost_usd: Decimal
    cancelled: bool
    model: str | None = None


@dataclass
class AwaitingReviewEvent:
    """Emitted when the session pauses for user approval. Two cases:

    1. **Skill deliverable** (kind='deliverable'): the agent called
       `AwaitReview` after producing a document/PRD/etc. The other
       fields (deliverable_kind, document_id, summary_for_user, url)
       describe the deliverable.

    2. **Pending action** (kind='send_email' / 'create_event'): a
       send-side tool staged a payload via `pending_actions`. The
       `pending_action` payload carries the preview so the ApprovalBar
       can render recipients/subject/body for emails or attendees/time
       for calendar events.

    The frontend swaps the chat input for an approval bar until the
    next user message resumes the session.
    """
    kind: str  # 'deliverable' | 'send_email' | 'create_event'
    deliverable_kind: str
    document_id: str | None
    summary_for_user: str
    url: str | None = None
    model: str | None = None
    pending_action: dict | None = None  # populated when kind != 'deliverable'


_SKILL_METADATA_KEYS = ("active_skill", "active_skill_phase", "pending_deliverable")


def _summarize_pending_action(kind: str, preview: dict) -> str:
    """One-line summary used as the AwaitingReviewEvent.summary_for_user
    fallback when the frontend hasn't loaded the full preview yet."""
    if kind == "send_email":
        recipients = ", ".join(preview.get("to") or [])
        return f"Send email '{preview.get('subject', '')}' to {recipients}"
    if kind == "create_event":
        attendees = ", ".join(preview.get("attendees") or [])
        return (
            f"Create event '{preview.get('summary', '')}' with invites to {attendees}"
        )
    return "Action staged for approval"

_APPROVE_WORDS = {"/approve", "approve", "approved", "looks good", "lgtm"}
_RESTART_WORDS = {"/restart", "restart", "start over", "cancel"}


def _classify_review_response(text: str) -> str | None:
    """Decide whether a reply during awaiting_review is approve/revise/restart.

    Returns one of 'approve', 'revise', 'restart', or None (free text —
    leave the pause in place). We lean strict on approve/restart (slash or
    exact phrase) and require an explicit `/revise` prefix for revisions.
    """
    stripped = text.strip()
    lower = stripped.lower()
    if not stripped:
        return None

    if lower in _APPROVE_WORDS or lower.startswith("/approve "):
        return "approve"
    if lower in _RESTART_WORDS or lower.startswith("/restart "):
        return "restart"
    if lower == "/revise" or lower.startswith("/revise ") or lower.startswith("/revise\n"):
        return "revise"
    return None


async def _apply_review_resolution(
    db: AsyncSession, session: Session, intent: str, user_text: str
) -> str:
    """Mutate session state for an approve/revise/restart reply.

    Returns a synthetic system note to inject into the LLM history
    (not persisted as a message). On approve of a pending_action this
    actually runs the staged action (sending an email, sending invites)
    and includes the result in the system note so the model can
    acknowledge it accurately.

    Async because executing a pending_action talks to Google APIs.
    """
    pending_action = get_pending_action(session)
    if pending_action is not None:
        return await _resolve_pending_action(
            db, session, intent, user_text, pending_action
        )

    # Existing deliverable-flow path (skill workflow).
    meta = dict(session.session_metadata or {})
    meta.pop("pending_deliverable", None)
    skill_name = meta.get("active_skill")

    if intent == "approve":
        meta.pop("active_skill", None)
        meta.pop("active_skill_phase", None)
        note = (
            "[SYSTEM] The user approved the deliverable"
            + (f" from the `{skill_name}` workflow" if skill_name else "")
            + ". The skill workflow is now complete. Briefly acknowledge the "
            "approval in one or two sentences and return to normal conversation. "
            "Do NOT re-draft or re-paste the deliverable."
        )
    elif intent == "revise":
        stripped = user_text.strip()
        revision = stripped[len("/revise"):].lstrip() if stripped.lower().startswith("/revise") else stripped
        note = (
            "[SYSTEM] The user requested revisions: "
            + (revision or "(no specific detail — ask them to clarify what to change)")
            + ". Apply the changes now (use `EditDocument` if a document is "
            "involved), then call `AwaitReview` again with an updated summary. "
            "Keep free-form text minimal — let the tool calls do the work."
        )
    else:  # restart
        meta.pop("active_skill", None)
        meta.pop("active_skill_phase", None)
        note = (
            "[SYSTEM] The user requested to restart. Drop any pending draft "
            "work and treat the next message as a fresh conversation. The "
            "skill has been cancelled."
        )

    session.status = "active"
    session.session_metadata = meta
    return note


async def _resolve_pending_action(
    db: AsyncSession,
    session: Session,
    intent: str,
    user_text: str,
    action: dict,
) -> str:
    """Approve / revise / restart for a staged send-side action.

    On approve we execute the action; if execution fails we leave the
    pause cleared but tell the model what went wrong so it can apologize
    and offer to retry.
    """
    kind = action.get("kind", "")
    tool_name = action.get("tool_name", "tool")

    if intent == "approve":
        try:
            success_summary = await execute_pending_action(db, session.user_id, action)
        except Exception as e:  # noqa: BLE001 — surface to model, not user
            logger.exception("pending_action %s execution failed", kind)
            clear_pending_action(session)
            session.status = "active"
            await _rewrite_staged_tool_result(
                db, session.id,
                f"[STAGED → FAILED] Execution of the staged {kind.replace('_', ' ')} "
                f"failed: {e}. The action did NOT complete.",
            )
            return (
                f"[SYSTEM] The user approved the {kind.replace('_', ' ')}, "
                f"but executing it failed: {e}. Apologize briefly and ask "
                f"if they want to retry. Do NOT call {tool_name} again "
                f"automatically — wait for confirmation."
            )
        clear_pending_action(session)
        session.status = "active"
        # Critical: rewrite the staged tool_result in the DB so the next
        # turn's LLM history shows a definitive "done" state instead of
        # the "[Pending approval]" marker. Without this, weak instruction
        # followers (Scout) re-call the tool after seeing the resume note,
        # causing duplicate sends.
        await _rewrite_staged_tool_result(
            db, session.id,
            f"[STAGED → APPROVED & EXECUTED] {success_summary} "
            f"This is the final result. The action is COMPLETE. Do not call "
            f"{tool_name} again.",
        )
        return (
            f"[SYSTEM — ACTION COMPLETE] {success_summary} "
            f"The previous {tool_name} call has been EXECUTED. There is "
            f"nothing left to do. Reply with ONE short sentence acknowledging "
            f"to the user. DO NOT call {tool_name} or any other tool — just text."
        )

    if intent == "revise":
        stripped = user_text.strip()
        revision = (
            stripped[len("/revise"):].lstrip()
            if stripped.lower().startswith("/revise")
            else stripped
        )
        clear_pending_action(session)
        session.status = "active"
        await _rewrite_staged_tool_result(
            db, session.id,
            f"[STAGED → REVISED] The user requested changes; the staged "
            f"{kind.replace('_', ' ')} was discarded.",
        )
        return (
            f"[SYSTEM] The user wants changes to the staged {kind.replace('_', ' ')}: "
            + (revision or "(no specific detail — ask them what to change)")
            + f". Re-call {tool_name} with the updated parameters; the new "
            "version will be staged for approval again. Keep free-form text minimal."
        )

    # restart
    clear_pending_action(session)
    session.status = "active"
    await _rewrite_staged_tool_result(
        db, session.id,
        f"[STAGED → CANCELLED] The user cancelled the staged "
        f"{kind.replace('_', ' ')}. Nothing was sent.",
    )
    return (
        f"[SYSTEM] The user cancelled the staged {kind.replace('_', ' ')}. "
        "Treat the next message as a fresh request. Do NOT re-stage."
    )


async def _rewrite_staged_tool_result(
    db: AsyncSession, session_id: UUID, replacement_output: str
) -> bool:
    """Find the most recent tool_result block that contains the "[Pending
    approval]" marker for this session and replace its output text. Used
    after approve/revise/restart to give the model a definitive end-state
    in its tool history (not a stale "Pending" message it might re-act on)."""
    stmt = (
        select(Message)
        .where(Message.session_id == session_id, Message.role == "tool")
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    candidates = list((await db.scalars(stmt)).all())
    for msg in candidates:
        new_blocks: list[dict] = []
        modified = False
        for block in msg.content or []:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and "[Pending approval]" in (block.get("output") or "")
            ):
                new_block = dict(block)
                new_block["output"] = replacement_output
                new_blocks.append(new_block)
                modified = True
            else:
                new_blocks.append(block)
        if modified:
            msg.content = new_blocks
            return True
    return False


def _apply_skill_detection(session: Session, user_text: str) -> None:
    """Update session.session_metadata based on the user's latest message.

    JSONB columns aren't auto-tracked for in-place mutation, so we always
    reassign the whole dict when anything changes.
    """
    current_meta: dict = dict(session.session_metadata or {})
    decision = detect_skill(user_text, current_meta)
    if decision is None:
        return

    if decision == CLEAR_SENTINEL:
        if any(k in current_meta for k in _SKILL_METADATA_KEYS):
            for k in _SKILL_METADATA_KEYS:
                current_meta.pop(k, None)
            session.session_metadata = current_meta
        return

    skill = get_skill(decision)
    if skill is None:
        return

    # Activating a new skill (or switching). Preserve phase if the same
    # skill is already active — the agent may just be continuing a turn.
    if current_meta.get("active_skill") == skill.name:
        return

    current_meta["active_skill"] = skill.name
    current_meta["active_skill_phase"] = skill.first_phase
    # A new skill invalidates any pending deliverable from a prior skill.
    current_meta.pop("pending_deliverable", None)
    session.session_metadata = current_meta


def _history_to_llm_messages(history: list[Message]) -> list[dict]:
    """Translate persisted Messages into the OpenAI Chat Completions wire format,
    preserving tool_use / tool_result blocks across turns.
    """
    out: list[dict] = []
    for msg in history:
        if msg.role == "user":
            text_parts = [
                b.get("text", "")
                for b in msg.content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            combined = "".join(text_parts).strip()
            if combined:
                out.append({"role": "user", "content": combined})

        elif msg.role == "assistant":
            text_parts: list[str] = []
            tool_calls: list[dict] = []
            for b in msg.content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    text_parts.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    tool_calls.append(
                        {
                            "id": b.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": b.get("name", ""),
                                "arguments": json.dumps(b.get("input") or {}),
                            },
                        }
                    )
            entry: dict[str, Any] = {"role": "assistant"}
            entry["content"] = "".join(text_parts) or None
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)

        elif msg.role == "tool":
            for b in msg.content:
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": b.get("tool_use_id", ""),
                        "content": b.get("output", ""),
                    }
                )
    return out


async def process_message(
    *,
    db: AsyncSession,
    redis: Redis,
    session_id: UUID,
    user_text: str,
) -> AsyncIterator[
    TextEvent | ToolStartEvent | ToolResultEvent | AwaitingReviewEvent | DoneEvent
]:
    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise ValueError(f"session {session_id} not found")

    # If the session was paused (status=awaiting_review from a prior
    # AwaitReview call), classify this reply as approve/revise/restart. If
    # recognised, clear pause state and queue a synthetic system note that
    # nudges the model toward the right resume behavior. Free-form replies
    # leave the pause in place — the user must use the approval buttons.
    resume_note: str | None = None
    if session.status == "awaiting_review":
        intent = _classify_review_response(user_text)
        if intent is not None:
            resume_note = await _apply_review_resolution(
                db, session, intent, user_text
            )

    # Skill detection runs before we load the system prompt so the active
    # skill (if any) shows up as Section 15. Rules (full logic in
    # app/core/skills.detect_skill):
    #   - slash command at start or multi-word keyword -> activate
    #   - /cancel-skill, /exit-skill, /restart -> clear
    #   - otherwise leave whatever's already in session_metadata
    _apply_skill_detection(session, user_text)

    # Per-turn model selection. Runs AFTER skill detection so that a turn
    # that just activated a skill (slash command) is routed to the heavy
    # model immediately, not only on the following turn.
    turn_model = select_model(user_text, session.session_metadata)

    stmt = (
        select(Message)
        .where(Message.session_id == session_id, Message.is_compacted.is_(False))
        .order_by(Message.turn_id, Message.created_at)
    )
    history = (await db.scalars(stmt)).all()

    system_prompt = await build_prompt(
        db=db,
        user_id=session.user_id,
        project_id=session.project_id,
        session_metadata=session.session_metadata or {},
    )
    llm_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(_history_to_llm_messages(list(history)))
    llm_messages.append({"role": "user", "content": user_text})
    if resume_note:
        llm_messages.append({"role": "system", "content": resume_note})

    turn_id = session.turn_count + 1

    user_message = Message(
        id=uuid4(),
        session_id=session_id,
        turn_id=turn_id,
        role="user",
        content=[{"type": "text", "text": user_text}],
    )
    db.add(user_message)
    session.turn_count = turn_id
    if session.title is None:
        session.title = user_text[:60] + ("…" if len(user_text) > 60 else "")
    await db.flush()
    await _safe_commit(db, session_id, stage="persist_user_message")

    await redis.delete(_cancel_key(session_id))

    tool_ctx = ToolContext(
        db=db,
        session_id=session_id,
        project_id=session.project_id,
        user_id=session.user_id,
    )
    ctx_token = set_context(tool_ctx)

    tool_specs = to_openai_tools(all_tools())
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = Decimal("0")
    cancelled = False

    for iteration in range(MAX_TOOL_ITERATIONS):
        assistant_chunks: list[str] = []
        stream_result: StreamResult | None = None

        async for event in stream_message(
            llm_messages, model=turn_model, tools=tool_specs
        ):
            if isinstance(event, StreamChunk):
                if await redis.exists(_cancel_key(session_id)):
                    cancelled = True
                    break
                assistant_chunks.append(event.text)
                yield TextEvent(text=event.text)
            elif isinstance(event, StreamResult):
                stream_result = event

        if cancelled or stream_result is None:
            break

        total_input_tokens += stream_result.input_tokens
        total_output_tokens += stream_result.output_tokens
        total_cost_usd += stream_result.cost_usd

        assistant_text = "".join(assistant_chunks)

        # Parse each tool call's JSON arguments up front. On parse failure we
        # still record the tool_use block (so the transcript is honest about
        # what the model emitted) but we'll feed an error back to the model
        # as the tool_result.
        # `multi_args` is populated only when Gemini concatenates several
        # parallel calls into one tool_call with `{..}{..}` arguments; in
        # that case we run the tool once per parsed object at execute time.
        parsed_calls: list[tuple[str, str, dict, str | None, list[dict] | None]] = []
        for tc in stream_result.tool_calls:
            raw_args = tc.arguments_json or ""
            multi_args: list[dict] | None = None
            try:
                parsed = json.loads(raw_args) if raw_args else {}
                parse_error: str | None = None
            except json.JSONDecodeError as e:
                salvaged = _split_concatenated_json_args(raw_args)
                if salvaged:
                    logger.info(
                        "salvaged %d concatenated JSON arg blobs for tool %s",
                        len(salvaged), tc.name,
                    )
                    multi_args = salvaged
                    parsed = salvaged[0]
                    parse_error = None
                else:
                    parsed = {}
                    parse_error = f"invalid JSON arguments: {e}. Raw: {raw_args!r}"
            if not isinstance(parsed, dict):
                parsed = {}
            parsed_calls.append((tc.id, tc.name, parsed, parse_error, multi_args))

        # Persist the assistant message (text + tool_use blocks)
        content_blocks: list[dict] = []
        if assistant_text:
            content_blocks.append({"type": "text", "text": assistant_text})
        for call_id, name, parsed, _err, _multi in parsed_calls:
            content_blocks.append(
                {"type": "tool_use", "id": call_id, "name": name, "input": parsed}
            )

        if content_blocks:
            assistant_message = Message(
                id=uuid4(),
                session_id=session_id,
                turn_id=turn_id,
                role="assistant",
                content=content_blocks,
            )
            db.add(assistant_message)

        # Append assistant message to the LLM history for the next turn
        assistant_entry: dict[str, Any] = {"role": "assistant"}
        assistant_entry["content"] = assistant_text or None
        if parsed_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(parsed)},
                }
                for call_id, name, parsed, _err, _multi in parsed_calls
            ]
        llm_messages.append(assistant_entry)

        # No tool calls → we're done for this turn
        if not parsed_calls:
            await _safe_commit(db, session_id, stage="persist_assistant_text")
            break

        # Track whether AwaitReview was called successfully — if so we pause
        # after executing the full batch instead of looping back to the model.
        await_review_args: dict | None = None

        # Execute each tool, stream start/result events, persist results
        for call_id, name, parsed, parse_error, multi_args in parsed_calls:
            yield ToolStartEvent(call_id=call_id, name=name, input=parsed)

            if parse_error is not None:
                output = f"Error: {parse_error}"
                is_error = True
            elif multi_args is not None:
                # Gemini concatenated N parallel calls into one. Run the
                # tool once per parsed blob and merge outputs so the model
                # sees all results keyed back to the single tool_call_id.
                parts: list[str] = []
                any_error = False
                for i, args in enumerate(multi_args, start=1):
                    if not isinstance(args, dict):
                        args = {}
                    o = await execute_tool(name, args)
                    if o.startswith("Error"):
                        any_error = True
                    parts.append(
                        f"[{name} call {i}/{len(multi_args)} — args: "
                        f"{json.dumps(args)}]\n{o}"
                    )
                output = "\n\n---\n\n".join(parts)
                is_error = any_error
            else:
                output = await execute_tool(name, parsed)
                is_error = output.startswith("Error")

            yield ToolResultEvent(
                call_id=call_id, name=name, output=output, is_error=is_error
            )

            tool_message = Message(
                id=uuid4(),
                session_id=session_id,
                turn_id=turn_id,
                role="tool",
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "tool_name": name,
                        "output": output,
                        "is_error": is_error,
                    }
                ],
            )
            db.add(tool_message)

            llm_messages.append(
                {"role": "tool", "tool_call_id": call_id, "content": output}
            )

            if name == "AwaitReview" and not is_error:
                await_review_args = parsed

        await _safe_commit(db, session_id, stage="persist_tool_results")

        # Pause cases (in priority order):
        #
        # 1. A staged pending_action (SendEmail / CreateCalendarEvent
        #    with attendees) — pause regardless of skill state. The
        #    user clicks Approve in the UI to actually execute the
        #    side effect.
        # 2. AwaitReview during an active skill — existing skill
        #    deliverable flow.
        #
        # Plain AwaitReview without an active skill is intentionally
        # NOT a pause trigger (Scout occasionally calls it spuriously
        # in casual chat).
        pending_action = get_pending_action(session)
        if pending_action is not None:
            preview = pending_action.get("preview") or {}
            kind = pending_action.get("kind") or ""
            summary = _summarize_pending_action(kind, preview)

            session.status = "awaiting_review"
            session.total_input_tokens += total_input_tokens
            session.total_output_tokens += total_output_tokens
            session.total_cost_usd = (session.total_cost_usd or Decimal("0")) + total_cost_usd
            await _safe_commit(db, session_id, stage="pause_for_action")

            yield AwaitingReviewEvent(
                kind=kind,
                deliverable_kind=kind,
                document_id=None,
                summary_for_user=summary,
                url=None,
                model=turn_model,
                pending_action=pending_action,
            )
            await redis.delete(_cancel_key(session_id))
            reset_context(ctx_token)
            return

        # A successful AwaitReview call ends the turn: the skill is signalling
        # it has a deliverable ready for review. We transition the session
        # into awaiting_review status, stash the pending deliverable, emit a
        # pause event, and return — no DoneEvent until the user replies.
        #
        # Guard: only pause when a skill is active. Casual chat that somehow
        # calls AwaitReview (shouldn't happen per SKILL.md instructions, but
        # Scout is imperfect) should NOT trap the user in an approval bar.
        if await_review_args is not None and (session.session_metadata or {}).get("active_skill"):
            document_id = (await_review_args.get("document_id") or None)
            # Look up the Google Docs URL if the deliverable is a Google doc,
            # so the approval bar can show a one-click "Open in Google Docs"
            # link rather than making the user expand the tool card.
            doc_url: str | None = None
            if document_id:
                try:
                    doc_url = await docs_router.get_document_url(
                        db, session.user_id, document_id
                    )
                except Exception:  # noqa: BLE001 — non-fatal, link is a nice-to-have
                    logger.exception("failed to resolve document url for %s", document_id)
                    doc_url = None

            deliverable = {
                "deliverable_kind": str(await_review_args.get("deliverable_kind") or ""),
                "document_id": document_id,
                "summary_for_user": str(await_review_args.get("summary_for_user") or ""),
                "url": doc_url,
            }
            meta = dict(session.session_metadata or {})
            meta["pending_deliverable"] = deliverable
            session.session_metadata = meta
            session.status = "awaiting_review"

            session.total_input_tokens += total_input_tokens
            session.total_output_tokens += total_output_tokens
            session.total_cost_usd = (session.total_cost_usd or Decimal("0")) + total_cost_usd
            await _safe_commit(db, session_id, stage="pause_for_review")

            yield AwaitingReviewEvent(
                kind="deliverable",
                deliverable_kind=deliverable["deliverable_kind"],
                document_id=deliverable["document_id"],
                summary_for_user=deliverable["summary_for_user"],
                url=doc_url,
                model=turn_model,
                pending_action=None,
            )
            await redis.delete(_cancel_key(session_id))
            reset_context(ctx_token)
            return
        # loop continues — give the model another turn to respond to tool results
    else:
        logger.warning(
            "session %s hit MAX_TOOL_ITERATIONS (%d)", session_id, MAX_TOOL_ITERATIONS
        )

    session.total_input_tokens += total_input_tokens
    session.total_output_tokens += total_output_tokens
    session.total_cost_usd = (session.total_cost_usd or Decimal("0")) + total_cost_usd

    await _safe_commit(db, session_id, stage="finalize_turn")
    await redis.delete(_cancel_key(session_id))
    reset_context(ctx_token)

    yield DoneEvent(
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        cost_usd=total_cost_usd,
        total_cost_usd=session.total_cost_usd,
        cancelled=cancelled,
        model=turn_model,
    )


async def cancel_session(redis: Redis, session_id: UUID) -> None:
    await redis.set(_cancel_key(session_id), "1", ex=60)
