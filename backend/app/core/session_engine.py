"""The conversation loop. Takes a user's message, runs it through Groq with
tools available, streams text + tool events back, persists every message.

Sprint 2 scope: tools + streaming tool events. System prompt is still a
placeholder — the real PM prompt lands in Chunk 5 of Sprint 2.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.core.local_store import LocalKVStore
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import credentials, model_registry
from app.core.documents import router as docs_router
from app.core.llm import stream_message
from app.core.llm_types import StreamChunk, StreamResult
from app.core.model_router import parse_deep_flag, select_model
from app.core.pending_actions import (
    clear_pending_action,
    execute_pending_action,
    get_pending_action,
    mark_action_executing,
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
from app.models import Message, Session, User

logger = logging.getLogger(__name__)

# Import tool modules so their `register(...)` calls run once at process start.
_load_builtin_tools()

MAX_TOOL_ITERATIONS = 8

# A weak model (e.g. Groq's Scout) sometimes EMITS a tool call as plain text —
# `SaveMemory("...", "...", "decision")` — instead of using the function-calling
# interface. The call never runs, nothing is saved, and there's no error: the
# user just sees a confusing line of pseudo-code. We detect that shape (a line
# starting with a REGISTERED tool name followed by `(`) and retry the turn once
# with a corrective nudge so the intended tool actually fires.
_TEXT_TOOL_CALL_RE = re.compile(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _looks_like_text_tool_call(text: str, tool_names: set[str]) -> bool:
    """True when `text` looks like a tool call written as prose — a line begins
    with `KnownToolName(`. Matching requires an EXACT registered tool name, so
    ordinary prose that merely mentions a tool by name does not trip it."""
    if not text:
        return False
    return any(
        m.group(1) in tool_names for m in _TEXT_TOOL_CALL_RE.finditer(text)
    )


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


class ApprovalPendingError(Exception):
    """Raised (before any persistence) when the session is paused on a staged
    side-effecting action and the user's reply isn't approve/revise/restart.
    The websocket layer maps this to an APPROVAL_REQUIRED error event — we
    refuse to run a model turn that could fire side effects while the
    approval bar is up (finding A6).
    """


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


# Per-session turn locks (finding A3). The websocket layer already rejects a
# second message for a busy session with TURN_IN_PROGRESS; this lock is the
# belt-and-braces guarantee that two concurrent process_message calls (e.g.
# from a future REST caller) can never interleave turn_count/seq assignment.
# Entries are never evicted — a Lock is ~100 bytes and this is a single-user
# desktop app, so growth is bounded by the user's session count.
_session_turn_locks: dict[UUID, asyncio.Lock] = {}


def _turn_lock(session_id: UUID) -> asyncio.Lock:
    lock = _session_turn_locks.get(session_id)
    if lock is None:
        lock = _session_turn_locks.setdefault(session_id, asyncio.Lock())
    return lock


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

# Exact-phrase word lists for review replies, matched after normalization
# (lowercase, trailing punctuation stripped, commas/apostrophes removed —
# so "Yes, send it!" and "don't" classify). Kept deliberately small and
# unambiguous: anything not listed is free text and leaves the pause in
# place rather than risking a misfired send or a dropped draft.
_APPROVE_WORDS = {
    "/approve", "approve", "approved", "looks good", "lgtm",
    "yes", "yes send it", "send it", "go ahead", "yes go ahead",
}
_RESTART_WORDS = {
    "/restart", "restart", "start over", "cancel",
    "no", "dont", "do not", "stop",
    "dont send", "do not send", "dont send it", "do not send it",
    "no dont", "never mind", "nevermind",
}


def _normalize_review_reply(text: str) -> str:
    """Fold a review reply into the canonical form the word lists use."""
    lower = text.strip().lower()
    lower = lower.replace("’", "").replace("'", "").replace(",", " ")
    lower = lower.rstrip(".!?…")
    return " ".join(lower.split())


def _classify_review_response(text: str) -> str | None:
    """Decide whether a reply during awaiting_review is approve/revise/restart.

    Returns one of 'approve', 'revise', 'restart', or None (free text —
    leave the pause in place). We lean strict on approve/restart (slash or
    exact phrase from the lists above) and require an explicit `/revise`
    prefix for revisions.
    """
    stripped = text.strip()
    lower = stripped.lower()
    if not stripped:
        return None

    normalized = _normalize_review_reply(stripped)
    if normalized in _APPROVE_WORDS or lower.startswith("/approve "):
        return "approve"
    if normalized in _RESTART_WORDS or lower.startswith("/restart "):
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
        if action.get("status") == "executing":
            # A previous approve was interrupted between the send and the
            # result being committed — the email/invite may or may not have
            # gone out. Never blindly re-execute; make the user verify.
            clear_pending_action(session)
            session.status = "active"
            await _rewrite_staged_tool_result(
                db, session.id,
                f"[STAGED → UNKNOWN] A previous approval of this "
                f"{kind.replace('_', ' ')} was interrupted mid-execution; it may "
                f"or may not have completed. Do not re-send without verifying.",
                action=action,
            )
            await _safe_commit(db, session.id, stage="resolve_interrupted_action")
            return (
                f"[SYSTEM] A previous approval of the {kind.replace('_', ' ')} was "
                f"interrupted mid-execution, so it may have already gone out. "
                f"Tell the user to verify (e.g. Gmail Sent folder / their "
                f"calendar) before retrying. Do NOT call {tool_name} again "
                f"automatically."
            )
        # Two-phase execute: commit the 'executing' stamp first so a crash
        # between the send and the result-commit can't double-send on the
        # next approve (see the guard above).
        mark_action_executing(session)
        await _safe_commit(db, session.id, stage="mark_action_executing")
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
                action=action,
            )
            await _safe_commit(db, session.id, stage="record_action_failure")
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
            action=action,
        )
        # Persist the executed state immediately — if anything later in the
        # turn fails, the cleared action and the definitive tool_result must
        # survive (the side effect already happened).
        await _safe_commit(db, session.id, stage="record_action_executed")
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
            action=action,
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
        action=action,
    )
    return (
        f"[SYSTEM] The user cancelled the staged {kind.replace('_', ' ')}. "
        "Treat the next message as a fresh request. Do NOT re-stage."
    )


def _block_matches_action(block: dict, action: dict | None) -> bool:
    """Does this "[Pending approval]" tool_result belong to `action`?

    With two actions staged in one batch (parallel SendEmail calls) the
    rewrite must target the SPECIFIC action being resolved, not whichever
    pending marker is found first (finding A4). Preferred match is the
    tool_call id recorded at stage time; legacy actions (no call_id) fall
    back to the tool name; action=None matches any pending marker (used by
    direct callers that predate per-action matching)."""
    if action is None:
        return True
    call_id = action.get("call_id")
    if call_id:
        return block.get("tool_use_id") == call_id
    tool_name = action.get("tool_name")
    if tool_name:
        return block.get("tool_name") == tool_name
    return True


async def _rewrite_staged_tool_result(
    db: AsyncSession,
    session_id: UUID,
    replacement_output: str,
    action: dict | None = None,
) -> bool:
    """Find the most recent tool_result block that contains the "[Pending
    approval]" marker for this session (and belongs to `action`, when given)
    and replace its output text. Used after approve/revise/restart to give
    the model a definitive end-state in its tool history (not a stale
    "Pending" message it might re-act on)."""
    stmt = (
        select(Message)
        .where(Message.session_id == session_id, Message.role == "tool")
        .order_by(Message.seq.desc())
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
                and _block_matches_action(block, action)
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
    # NOTE (A22): active_skill_phase is no longer written. It was set to the
    # first phase at activation and never advanced, so the prompt told the
    # model "current phase: intake" on every turn of a workflow. The prompt
    # now lists the phases without claiming a position; the key stays in
    # _SKILL_METADATA_KEYS so legacy sessions still get it cleaned up.
    current_meta.pop("active_skill_phase", None)
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
                    call = {
                        "id": b.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": b.get("name", ""),
                            "arguments": json.dumps(b.get("input") or {}),
                        },
                    }
                    # Gemini (native SDK) requires its opaque thought_signature
                    # replayed on historical calls; persisted with the block
                    # (item 19). google_genai_client reads this key; the
                    # OpenAI-compat clients strip it before the wire.
                    if b.get("thought_signature"):
                        call["thought_signature"] = b["thought_signature"]
                    tool_calls.append(call)
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


# ---- token estimation + history budgeting (Phase 1 item 10, C5/A8) ----

# Context-window room reserved for the model's own response.
RESPONSE_TOKEN_RESERVE = 2048
# For raw env-override models that aren't in the registry. Every registered
# model is ≥128k, so this is the conservative floor.
DEFAULT_CONTEXT_WINDOW = 128_000


def _estimate_tokens(text: str) -> int:
    """Crude but dependable token estimate: ~4 characters per token (the
    common English average across the providers we route to). We only need
    budget-level accuracy for the sliding window — the 2k response reserve
    absorbs the estimation error."""
    return max(1, len(text) // 4) if text else 0


def _estimate_content_tokens(blocks: list) -> int:
    """Estimate for a Message's content blocks: text, tool inputs (JSON, the
    way the provider sees them), and tool outputs — plus a few tokens of
    structural overhead per message (role markers etc.)."""
    total = 0
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            total += _estimate_tokens(block.get("text") or "")
        elif btype == "tool_use":
            total += _estimate_tokens(block.get("name") or "")
            total += _estimate_tokens(json.dumps(block.get("input") or {}))
        elif btype == "tool_result":
            total += _estimate_tokens(block.get("output") or "")
    return total + 4


def _context_window_for(model: str) -> int:
    entry = model_registry.get_model(model)
    return entry.context_window if entry is not None else DEFAULT_CONTEXT_WINDOW


def _truncate_history_to_budget(
    history: list[Message], budget_tokens: int
) -> tuple[list[Message], int]:
    """Sliding-window truncation: walk turns newest→oldest accumulating
    token estimates and drop whole TURNS beyond the budget. Never splits a
    turn — an assistant tool_use without its paired tool_results (or vice
    versa) makes the rebuilt provider history invalid.

    Returns (kept_history, omitted_turn_count). The newest turn is always
    kept, even when over budget on its own — better to let the provider
    reject one pathological turn than to send the model nothing.

    NOTE: deliberately just a window. Summarize-then-mark compaction
    (Message.is_compacted, which the history query already filters on) is
    left for a later phase.
    """
    if not history:
        return history, 0

    turns: list[list[Message]] = []
    for msg in history:  # already ordered by (turn_id, seq)
        if turns and turns[-1][0].turn_id == msg.turn_id:
            turns[-1].append(msg)
        else:
            turns.append([msg])

    kept_rev: list[list[Message]] = []
    used = 0
    for turn in reversed(turns):
        cost = sum(
            m.token_count_estimate
            if m.token_count_estimate is not None
            # Legacy rows (pre-Phase-1) have no stored estimate.
            else _estimate_content_tokens(m.content or [])
            for m in turn
        )
        if kept_rev and used + cost > budget_tokens:
            break
        used += cost
        kept_rev.append(turn)

    omitted = len(turns) - len(kept_rev)
    kept = [m for turn in reversed(kept_rev) for m in turn]
    return kept, omitted


async def process_message(
    *,
    db: AsyncSession,
    kv: LocalKVStore,
    session_id: UUID,
    user_text: str,
) -> AsyncIterator[
    TextEvent | ToolStartEvent | ToolResultEvent | AwaitingReviewEvent | DoneEvent
]:
    """Run one turn, serialized per session (see _turn_lock). Thin wrapper so
    the lock covers the inner generator's whole lifetime, including the
    cleanup in its finally block when the consumer aclose()s us."""
    async with _turn_lock(session_id):
        agen = _process_message_locked(
            db=db, kv=kv, session_id=session_id, user_text=user_text
        )
        try:
            async for event in agen:
                yield event
        finally:
            # Deterministic close: a consumer that bails early (disconnect,
            # task cancel) must run the inner generator's finally NOW, while
            # we still hold the lock — not whenever GC finalizes it.
            await agen.aclose()


async def _process_message_locked(
    *,
    db: AsyncSession,
    kv: LocalKVStore,
    session_id: UUID,
    user_text: str,
) -> AsyncIterator[
    TextEvent | ToolStartEvent | ToolResultEvent | AwaitingReviewEvent | DoneEvent
]:
    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise ValueError(f"session {session_id} not found")

    # `/deep` escape hatch: strip the flag up front so the cleaned text is what
    # we classify, persist, and send to the model; `is_deep` forces this turn
    # to the heavy model below.
    is_deep, user_text = parse_deep_flag(user_text)

    # If the session was paused (status=awaiting_review from a prior
    # AwaitReview call), classify this reply as approve/revise/restart. If
    # recognised, clear pause state and queue a synthetic system note that
    # nudges the model toward the right resume behavior. Free-form replies
    # leave the pause in place — the user must use the approval buttons.
    #
    # If MORE actions remain staged after resolving one (parallel sends in
    # one batch), we re-pause on the next one instead of resuming a model
    # turn: `next_staged_action` short-circuits below, right after the user
    # message is persisted.
    resume_note: str | None = None
    next_staged_action: dict | None = None
    if session.status == "awaiting_review":
        intent = _classify_review_response(user_text)
        if intent is None and get_pending_action(session) is not None:
            # Paused on a staged SIDE EFFECT and the reply isn't a
            # recognisable resolution: refuse to run a model turn that could
            # fire side-effecting tools while the approval bar is up
            # (finding A6). Deliverable pauses (no staged action) keep the
            # old behavior — a free-text turn runs with the pause intact.
            raise ApprovalPendingError(
                "This session is waiting for your decision on a staged "
                "action. Use the approval bar (Approve / Make changes / "
                "Cancel), or reply /approve, /revise <changes>, or /restart."
            )
        if intent is not None:
            resume_note = await _apply_review_resolution(
                db, session, intent, user_text
            )
            next_staged_action = get_pending_action(session)
            meta = dict(session.session_metadata or {})
            queued_notes = list(meta.get("queued_resume_notes") or [])
            if next_staged_action is not None:
                # Stay paused for the next staged action. The resolution note
                # can't reach the model yet (no model call this turn), so park
                # it; it's delivered with the final resume.
                session.status = "awaiting_review"
                queued_notes.append(resume_note)
                meta["queued_resume_notes"] = queued_notes
                session.session_metadata = meta
                resume_note = None
            elif queued_notes:
                # Last action resolved — deliver the parked notes too.
                meta.pop("queued_resume_notes", None)
                session.session_metadata = meta
                resume_note = "\n\n".join([*queued_notes, resume_note])

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
    # User preferences from `users.preferences.{light_model,heavy_model}`
    # override env-var defaults when set (Sprint 6 Chunk C).
    turn_user = await db.scalar(select(User).where(User.id == session.user_id))
    # Per-user configured providers (stored key OR env) so a model the user
    # picked with only a stored key is still honored. Also used to resolve the
    # actual key to pass to the provider client (C8 Connections).
    configured = await credentials.configured_llm_providers(db, session.user_id)
    turn_model = select_model(
        user_text,
        session.session_metadata,
        user_preferences=(turn_user.preferences if turn_user else None),
        configured_providers=configured,
        force_heavy=is_deep,
    )
    turn_api_key = await credentials.resolve_api_key(
        db, session.user_id, credentials.llm_provider_for_model(turn_model)
    )
    # Keep the session row's provider/model columns pointing at the brain that
    # actually served the latest turn (finding A20: they were write-once
    # defaults that never matched reality). Committed with the user message.
    session.llm_model = turn_model
    session.llm_provider = model_registry.infer_provider(turn_model)

    stmt = (
        select(Message)
        .where(Message.session_id == session_id, Message.is_compacted.is_(False))
        .order_by(Message.turn_id, Message.seq)
    )
    history = (await db.scalars(stmt)).all()

    # Per-session monotonic message counter. created_at can't order messages
    # within a turn (1-second resolution on SQLite), and a tool result sorting
    # before its assistant tool_use call makes the rebuilt provider history
    # invalid — permanently. Every message this turn persists gets the next
    # value.
    max_seq = await db.scalar(
        select(func.max(Message.seq)).where(Message.session_id == session_id)
    )
    next_seq = (max_seq or 0) + 1

    def _take_seq() -> int:
        nonlocal next_seq
        value = next_seq
        next_seq += 1
        return value

    system_prompt = await build_prompt(
        db=db,
        user_id=session.user_id,
        project_id=session.project_id,
        session_metadata=session.session_metadata or {},
    )
    # Sliding-window budget: the model's context minus the static prompt, the
    # incoming user message, and room for the response. Whole turns beyond the
    # budget are dropped oldest-first (see _truncate_history_to_budget) —
    # without this, long sessions grow until the provider hard-rejects every
    # turn.
    budget = (
        _context_window_for(turn_model)
        - _estimate_tokens(system_prompt)
        - _estimate_tokens(user_text)
        - RESPONSE_TOKEN_RESERVE
    )
    window, omitted_turns = _truncate_history_to_budget(list(history), budget)
    if omitted_turns:
        logger.info(
            "session %s: omitting %d oldest turn(s) to fit %s's context window",
            session_id, omitted_turns, turn_model,
        )
    llm_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if omitted_turns:
        # Tell the model the transcript is windowed so it doesn't treat the
        # cut point as the actual start of the conversation.
        llm_messages.append(
            {
                "role": "system",
                "content": (
                    f"[Earlier conversation truncated: {omitted_turns} older "
                    f"turn(s) omitted to fit the context window.]"
                ),
            }
        )
    llm_messages.extend(_history_to_llm_messages(window))
    llm_messages.append({"role": "user", "content": user_text})
    if resume_note:
        llm_messages.append({"role": "system", "content": resume_note})

    turn_id = session.turn_count + 1

    user_message = Message(
        id=uuid4(),
        session_id=session_id,
        turn_id=turn_id,
        seq=_take_seq(),
        role="user",
        content=[{"type": "text", "text": user_text}],
        token_count_estimate=_estimate_content_tokens(
            [{"type": "text", "text": user_text}]
        ),
    )
    db.add(user_message)
    session.turn_count = turn_id
    if session.title is None:
        session.title = user_text[:60] + ("…" if len(user_text) > 60 else "")
    await db.flush()
    await _safe_commit(db, session_id, stage="persist_user_message")

    await kv.delete(_cancel_key(session_id))

    # Re-pause: the resolved action wasn't the last one staged. Emit the
    # approval event for the next queued action and end the turn — no model
    # call until the whole queue is resolved.
    if next_staged_action is not None:
        next_kind = next_staged_action.get("kind") or ""
        yield AwaitingReviewEvent(
            kind=next_kind,
            deliverable_kind=next_kind,
            document_id=None,
            summary_for_user=_summarize_pending_action(
                next_kind, next_staged_action.get("preview") or {}
            ),
            url=None,
            model=turn_model,
            pending_action=next_staged_action,
        )
        return

    tool_ctx = ToolContext(
        db=db,
        session_id=session_id,
        project_id=session.project_id,
        user_id=session.user_id,
    )
    ctx_token = set_context(tool_ctx)

    tool_specs = to_openai_tools(all_tools())
    known_tool_names = {
        spec["function"]["name"]
        for spec in tool_specs
        if isinstance(spec, dict) and isinstance(spec.get("function"), dict)
    }
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = Decimal("0")
    cancelled = False
    # One-shot guard for the tool-call-as-text quirk (see _looks_like_text_tool_call):
    # if a turn ends with a tool call written as plain text, we retry once with a
    # corrective nudge. The flag stops that from looping on a model that repeats it.
    text_toolcall_retry_used = False
    # Assistant text streamed before a mid-stream cancel. Persisted (with an
    # interruption marker) at the end of the turn so a reload doesn't lose
    # text the user already saw (finding A9/A10).
    cancelled_partial_text = ""

    # try/finally so the tool contextvar and the cancel flag are ALWAYS
    # cleaned up — on provider errors, commit failures, and the consumer
    # closing us mid-stream alike (finding A9: they used to leak on any
    # exception).
    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            # Cancel check at the top of every iteration (finding A2): a flag
            # set while the previous batch's tools were running must stop the
            # loop before we pay for another model call.
            if await kv.exists(_cancel_key(session_id)):
                cancelled = True
                break

            assistant_chunks: list[str] = []
            stream_result: StreamResult | None = None

            stream = stream_message(
                llm_messages, model=turn_model, tools=tool_specs, api_key=turn_api_key
            )
            try:
                async for event in stream:
                    if isinstance(event, StreamChunk):
                        if await kv.exists(_cancel_key(session_id)):
                            cancelled = True
                            break
                        assistant_chunks.append(event.text)
                        yield TextEvent(text=event.text)
                    elif isinstance(event, StreamResult):
                        stream_result = event
            finally:
                # Close the provider stream explicitly: on cancel we bail out
                # mid-iteration and must not leave a dangling HTTP stream
                # (no-op when the stream ran to exhaustion).
                await stream.aclose()

            # Record usage/cost as soon as a StreamResult exists — even on a
            # cancelled iteration (finding A10): the tokens were still spent.
            if stream_result is not None:
                total_input_tokens += stream_result.input_tokens
                total_output_tokens += stream_result.output_tokens
                total_cost_usd += stream_result.cost_usd

            if cancelled or stream_result is None:
                cancelled_partial_text = "".join(assistant_chunks)
                break

            assistant_text = "".join(assistant_chunks)

            # Parse each tool call's JSON arguments up front. On parse failure we
            # still record the tool_use block (so the transcript is honest about
            # what the model emitted) but we'll feed an error back to the model
            # as the tool_result.
            # `multi_args` is populated only when Gemini concatenates several
            # parallel calls into one tool_call with `{..}{..}` arguments; in
            # that case we run the tool once per parsed object at execute time.
            # `signature` is the Gemini thought_signature (base64, item 19) —
            # persisted with the tool_use block so it replays across restarts.
            parsed_calls: list[
                tuple[str, str, dict, str | None, list[dict] | None, str | None]
            ] = []
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
                parsed_calls.append(
                    (tc.id, tc.name, parsed, parse_error, multi_args,
                     getattr(tc, "thought_signature", None))
                )

            # Persist the assistant message (text + tool_use blocks)
            content_blocks: list[dict] = []
            if assistant_text:
                content_blocks.append({"type": "text", "text": assistant_text})
            for call_id, name, parsed, _err, _multi, signature in parsed_calls:
                block = {"type": "tool_use", "id": call_id, "name": name, "input": parsed}
                if signature:
                    block["thought_signature"] = signature
                content_blocks.append(block)

            if content_blocks:
                assistant_message = Message(
                    id=uuid4(),
                    session_id=session_id,
                    turn_id=turn_id,
                    seq=_take_seq(),
                    role="assistant",
                    content=content_blocks,
                    token_count_estimate=_estimate_content_tokens(content_blocks),
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
                        # The same-turn follow-up request must also carry the
                        # Gemini thought_signature (item 19).
                        **({"thought_signature": signature} if signature else {}),
                    }
                    for call_id, name, parsed, _err, _multi, signature in parsed_calls
                ]
            llm_messages.append(assistant_entry)

            # No tool calls → we're done for this turn — UNLESS the model wrote
            # a tool call as plain text (weak-model quirk). Retry once with a
            # corrective nudge so the intended tool actually runs instead of
            # silently dropping it (the user would otherwise see a bogus
            # `SaveMemory(...)` line and nothing saved).
            if not parsed_calls:
                if (
                    assistant_text
                    and not text_toolcall_retry_used
                    and _looks_like_text_tool_call(assistant_text, known_tool_names)
                ):
                    text_toolcall_retry_used = True
                    logger.info(
                        "detected tool-call-as-text; retrying turn with a corrective nudge"
                    )
                    llm_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "That looks like a tool call written as plain text. "
                                "Do not write tool calls as text — actually invoke the "
                                "tool now using the function-calling interface."
                            ),
                        }
                    )
                    continue
                await _safe_commit(db, session_id, stage="persist_assistant_text")
                break

            # Track whether AwaitReview was called successfully — if so we pause
            # after executing the full batch instead of looping back to the model.
            await_review_args: dict | None = None

            # Execute each tool, stream start/result events, persist results
            for call_id, name, parsed, parse_error, multi_args, _sig in parsed_calls:
                # Cancel check before each tool execution (finding A2). We
                # still emit + persist a result for this and every remaining
                # call: the assistant message with their tool_use blocks is
                # already persisted, and a tool_use without a paired
                # tool_result makes the rebuilt provider history invalid.
                if not cancelled and await kv.exists(_cancel_key(session_id)):
                    cancelled = True

                yield ToolStartEvent(call_id=call_id, name=name, input=parsed)
                # Staging tools read this so their pending_action records
                # which tool_result to rewrite at resolution time.
                tool_ctx.current_call_id = call_id

                if cancelled:
                    output = (
                        "[Cancelled] The user stopped this turn before this "
                        "tool ran. It did NOT execute."
                    )
                    is_error = True
                elif parse_error is not None:
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

                tool_content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "tool_name": name,
                        "output": output,
                        "is_error": is_error,
                    }
                ]
                tool_message = Message(
                    id=uuid4(),
                    session_id=session_id,
                    turn_id=turn_id,
                    seq=_take_seq(),
                    role="tool",
                    content=tool_content,
                    token_count_estimate=_estimate_content_tokens(tool_content),
                )
                db.add(tool_message)

                llm_messages.append(
                    {"role": "tool", "tool_call_id": call_id, "content": output}
                )

                if name == "AwaitReview" and not is_error:
                    await_review_args = parsed

            await _safe_commit(db, session_id, stage="persist_tool_results")

            # One more check after the batch: a cancel that arrived while the
            # LAST tool ran would otherwise be ignored by a pause path below
            # (which returns before the next top-of-loop check).
            if not cancelled and await kv.exists(_cancel_key(session_id)):
                cancelled = True

            if cancelled:
                # Side effects staged earlier in this batch must not survive
                # a stop — the user explicitly halted the turn. Rewrite each
                # one's "[Pending approval]" tool result so the model can't
                # act on a stale staged state next turn.
                discarded_any = False
                while (discarded := clear_pending_action(session)) is not None:
                    await _rewrite_staged_tool_result(
                        db, session_id,
                        "[STAGED → CANCELLED] The user stopped this turn; the "
                        "staged action was discarded. Nothing was sent.",
                        action=discarded,
                    )
                    discarded_any = True
                if discarded_any:
                    await _safe_commit(
                        db, session_id, stage="discard_staged_on_cancel"
                    )
                break

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
                return
            # loop continues — give the model another turn to respond to tool results
        else:
            logger.warning(
                "session %s hit MAX_TOOL_ITERATIONS (%d)", session_id, MAX_TOOL_ITERATIONS
            )
            # Finding A11: don't end the turn in silence. One final model
            # call WITHOUT tools so the user gets a wrap-up instead of a
            # dead stop. tools=None means the model physically cannot loop
            # further — this is capped at exactly one extra call. Best
            # effort: a provider failure here must not torch the (already
            # committed) tool work, so errors are logged and swallowed.
            llm_messages.append(
                {
                    "role": "system",
                    "content": (
                        "[SYSTEM] You have hit the tool-call limit for this "
                        "turn and no more tools are available. Wrap up now: "
                        "summarize in a few sentences what you accomplished "
                        "and what remains to be done, and tell the user to "
                        "send a follow-up message to continue."
                    ),
                }
            )
            wrap_chunks: list[str] = []
            wrap_result: StreamResult | None = None
            wrap_stream = stream_message(
                llm_messages, model=turn_model, tools=None, api_key=turn_api_key
            )
            try:
                async for event in wrap_stream:
                    if isinstance(event, StreamChunk):
                        if await kv.exists(_cancel_key(session_id)):
                            cancelled = True
                            break
                        wrap_chunks.append(event.text)
                        yield TextEvent(text=event.text)
                    elif isinstance(event, StreamResult):
                        wrap_result = event
            except Exception:  # noqa: BLE001 — wrap-up is best-effort
                logger.exception(
                    "wrap-up call after MAX_TOOL_ITERATIONS failed for %s",
                    session_id,
                )
            finally:
                await wrap_stream.aclose()
            if wrap_result is not None:
                total_input_tokens += wrap_result.input_tokens
                total_output_tokens += wrap_result.output_tokens
                total_cost_usd += wrap_result.cost_usd
            wrap_text = "".join(wrap_chunks)
            if cancelled:
                # Reuse the cancel path's partial-text persistence below.
                cancelled_partial_text = wrap_text
            elif wrap_text:
                db.add(
                    Message(
                        id=uuid4(),
                        session_id=session_id,
                        turn_id=turn_id,
                        seq=_take_seq(),
                        role="assistant",
                        content=[{"type": "text", "text": wrap_text}],
                        token_count_estimate=_estimate_content_tokens(
                            [{"type": "text", "text": wrap_text}]
                        ),
                    )
                )

        # On cancel, persist whatever the model streamed before the stop with
        # an explicit interruption marker — a reload must not lose text the
        # user already saw, and later turns' history should show the cutoff.
        if cancelled and cancelled_partial_text:
            interrupted_content = [
                {
                    "type": "text",
                    "text": cancelled_partial_text
                    + "\n\n_[Response interrupted — stopped by the user.]_",
                }
            ]
            db.add(
                Message(
                    id=uuid4(),
                    session_id=session_id,
                    turn_id=turn_id,
                    seq=_take_seq(),
                    role="assistant",
                    content=interrupted_content,
                    token_count_estimate=_estimate_content_tokens(
                        interrupted_content
                    ),
                )
            )

        session.total_input_tokens += total_input_tokens
        session.total_output_tokens += total_output_tokens
        session.total_cost_usd = (session.total_cost_usd or Decimal("0")) + total_cost_usd

        await _safe_commit(db, session_id, stage="finalize_turn")

        yield DoneEvent(
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=total_cost_usd,
            total_cost_usd=session.total_cost_usd,
            cancelled=cancelled,
            model=turn_model,
        )
    finally:
        reset_context(ctx_token)
        await kv.delete(_cancel_key(session_id))


async def cancel_session(kv: LocalKVStore, session_id: UUID) -> None:
    await kv.set(_cancel_key(session_id), "1", ex=60)
