"""Engine integration tests — plan item 29 (T1).

Drives the real `process_message` loop against the SQLite `db`/`seeded`
fixtures with `stream_message` replaced by scripted StreamChunk/StreamResult
sequences. Everything else is real: skill detection, model routing, message
persistence (turn_id/seq), the pause-and-review state machine, pending-action
staging through the real SendEmail tool, and the per-stage commit protocol.

Replaces the manual smoke scripts `scripts/try_pause.py`,
`scripts/try_pause_action.py` (staging/approve/revise paths, with the real
Gmail send stubbed), and the loop mechanics of `scripts/try_tool_loop.py`.
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import session_engine
from app.core.groq_client import StreamChunk, StreamResult, ToolCall
from app.core.local_store import LocalKVStore
from app.core.session_engine import (
    AwaitingReviewEvent,
    CommitFailedError,
    DoneEvent,
    MAX_TOOL_ITERATIONS,
    TextEvent,
    ToolResultEvent,
    ToolStartEvent,
    _cancel_key,
    _history_to_llm_messages,
    _rewrite_staged_tool_result,
    process_message,
)
from app.core.tools import REGISTRY, Tool, register
from app.models import Message, Session

# asyncio_mode = "auto" (pyproject) picks up the async tests; no module-wide
# asyncio mark, because the _history_to_llm_messages tests below are sync.


# ---------- shared helpers + fixtures ----------


@pytest.fixture(autouse=True)
def _tmp_memory_root(tmp_path, monkeypatch):
    """build_prompt reads the project memory dir; keep it out of the repo."""
    monkeypatch.setattr(settings, "memory_root", str(tmp_path / "memory"))


@pytest.fixture
def kv() -> LocalKVStore:
    return LocalKVStore()


@pytest.fixture
def echo_tool():
    """A deterministic throwaway tool so tool-loop tests don't depend on any
    real tool's behavior. Removed from the global registry afterwards."""

    async def _handler(args: dict) -> str:
        return f"echo:{args.get('value', '')}"

    tool = register(
        Tool(
            name="TestEcho",
            description="test-only echo tool",
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
            },
            handler=_handler,
        )
    )
    yield tool
    REGISTRY.pop("TestEcho", None)


async def _make_session(db: AsyncSession, seeded: dict, **kwargs) -> Session:
    session = Session(
        id=uuid4(),
        user_id=seeded["user"].id,
        project_id=seeded["project"].id,
        **kwargs,
    )
    db.add(session)
    await db.commit()
    return session


def _result(
    text: str = "",
    tool_calls: list[ToolCall] | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
    cost_usd: Decimal = Decimal("0.001"),
) -> StreamResult:
    return StreamResult(
        text=text,
        tool_calls=tool_calls or [],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        finish_reason="tool_calls" if tool_calls else "stop",
    )


def _scripted_stream(*turns):
    """Build a stream_message stand-in. Each positional arg is one model
    iteration: a list of StreamChunk/StreamResult events to yield. The stub
    records every call's kwargs (incl. a snapshot of `messages`) on `.calls`.
    """
    queue = [list(t) for t in turns]
    calls: list[dict] = []

    async def _stub(messages, model=None, tools=None, api_key=None):
        calls.append(
            {
                "messages": [dict(m) for m in messages],
                "model": model,
                "tools": tools,
                "api_key": api_key,
            }
        )
        assert queue, "stream_message called more times than scripted"
        for event in queue.pop(0):
            yield event

    _stub.calls = calls
    return _stub


async def _run_turn(db, kv, session_id, text) -> list:
    return [
        event
        async for event in process_message(
            db=db, kv=kv, session_id=session_id, user_text=text
        )
    ]


async def _messages_for(db: AsyncSession, session_id) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.turn_id, Message.seq)
    )
    return list((await db.scalars(stmt)).all())


# ---------- (a) plain text turn ----------


async def test_plain_text_turn_events_and_persistence(db, seeded, kv, monkeypatch):
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        [
            StreamChunk(text="Hello "),
            StreamChunk(text="world"),
            _result(text="Hello world", input_tokens=11, output_tokens=7,
                    cost_usd=Decimal("0.002")),
        ]
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "hi there")

    # Events in order: the two text deltas, then exactly one DoneEvent.
    assert [type(e) for e in events] == [TextEvent, TextEvent, DoneEvent]
    assert [e.text for e in events[:2]] == ["Hello ", "world"]
    done = events[-1]
    assert done.input_tokens == 11
    assert done.output_tokens == 7
    assert done.cost_usd == Decimal("0.002")
    assert done.cancelled is False
    assert done.model  # routed model id is reported

    # Persistence: user + assistant rows on turn 1 with monotonic seq.
    messages = await _messages_for(db, session.id)
    assert [(m.role, m.turn_id) for m in messages] == [("user", 1), ("assistant", 1)]
    assert [m.seq for m in messages] == [1, 2]
    assert messages[0].content == [{"type": "text", "text": "hi there"}]
    assert messages[1].content == [{"type": "text", "text": "Hello world"}]

    # Usage/cost accumulated onto the session; title set from the first message.
    await db.refresh(session)
    assert session.turn_count == 1
    assert session.total_input_tokens == 11
    assert session.total_output_tokens == 7
    assert session.total_cost_usd == Decimal("0.002")
    assert done.total_cost_usd == Decimal("0.002")
    assert session.title == "hi there"

    # The model saw [system, user] — no phantom history on a fresh session.
    sent = stub.calls[0]["messages"]
    assert [m["role"] for m in sent] == ["system", "user"]
    assert sent[1]["content"] == "hi there"


async def test_second_turn_includes_history_and_continues_seq(
    db, seeded, kv, monkeypatch
):
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        [StreamChunk(text="one"), _result(text="one")],
        [StreamChunk(text="two"), _result(text="two", cost_usd=Decimal("0.003"))],
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    await _run_turn(db, kv, session.id, "first")
    await _run_turn(db, kv, session.id, "second")

    messages = await _messages_for(db, session.id)
    assert [(m.role, m.turn_id, m.seq) for m in messages] == [
        ("user", 1, 1),
        ("assistant", 1, 2),
        ("user", 2, 3),
        ("assistant", 2, 4),
    ]

    # The second model call replays turn 1 from the DB.
    sent = stub.calls[1]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1]["content"] == "first"
    assert sent[2]["content"] == "one"
    assert sent[3]["content"] == "second"

    await db.refresh(session)
    assert session.turn_count == 2
    assert session.total_cost_usd == Decimal("0.004")


# ---------- (b) tool-call turn ----------


async def test_tool_call_turn_events_persistence_and_followup(
    db, seeded, kv, monkeypatch, echo_tool
):
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        # Iteration 1: the model calls the tool (no text).
        [
            _result(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="TestEcho",
                        arguments_json='{"value": "ping"}',
                    )
                ],
                input_tokens=20,
                output_tokens=4,
            )
        ],
        # Iteration 2: the model answers from the tool result.
        [StreamChunk(text="pong"), _result(text="pong", input_tokens=30, output_tokens=2)],
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "run the echo tool")

    assert [type(e) for e in events] == [
        ToolStartEvent,
        ToolResultEvent,
        TextEvent,
        DoneEvent,
    ]
    start, result = events[0], events[1]
    assert (start.call_id, start.name, start.input) == ("call_1", "TestEcho", {"value": "ping"})
    assert (result.call_id, result.output, result.is_error) == ("call_1", "echo:ping", False)

    # Usage accumulates across both model iterations.
    done = events[-1]
    assert done.input_tokens == 50
    assert done.output_tokens == 6

    # Persistence: user, assistant(tool_use), tool, assistant(text) — one turn,
    # seq strictly increasing across the whole batch.
    messages = await _messages_for(db, session.id)
    assert [m.role for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert all(m.turn_id == 1 for m in messages)
    assert [m.seq for m in messages] == [1, 2, 3, 4]
    assert messages[1].content == [
        {"type": "tool_use", "id": "call_1", "name": "TestEcho", "input": {"value": "ping"}}
    ]
    assert messages[2].content == [
        {
            "type": "tool_result",
            "tool_use_id": "call_1",
            "tool_name": "TestEcho",
            "output": "echo:ping",
            "is_error": False,
        }
    ]

    # The second model iteration received the assistant tool_calls entry and
    # the tool result, properly paired by id.
    second = stub.calls[1]["messages"]
    assert second[-2]["role"] == "assistant"
    assert second[-2]["tool_calls"][0]["id"] == "call_1"
    assert json.loads(second[-2]["tool_calls"][0]["function"]["arguments"]) == {"value": "ping"}
    assert second[-1] == {"role": "tool", "tool_call_id": "call_1", "content": "echo:ping"}


async def test_malformed_tool_arguments_fed_back_as_error(
    db, seeded, kv, monkeypatch, echo_tool
):
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        [
            _result(
                tool_calls=[
                    ToolCall(id="call_bad", name="TestEcho", arguments_json="{not json")
                ]
            )
        ],
        [_result(text="recovered")],
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "go")

    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert tool_results[0].is_error is True
    assert tool_results[0].output.startswith("Error: invalid JSON arguments")
    # The transcript still records the (empty-input) tool_use honestly.
    messages = await _messages_for(db, session.id)
    assert messages[1].content[0] == {
        "type": "tool_use", "id": "call_bad", "name": "TestEcho", "input": {},
    }


# ---------- (c) AwaitReview deliverable pause + approve/revise/restart ----------


_AWAIT_REVIEW_CALL = ToolCall(
    id="call_ar",
    name="AwaitReview",
    arguments_json=json.dumps(
        {"deliverable_kind": "prd", "summary_for_user": "Drafted the PRD."}
    ),
)


async def _pause_on_deliverable(db, seeded, kv, monkeypatch) -> tuple[Session, list]:
    """Run one turn that ends in an AwaitReview pause; returns (session, events)."""
    session = await _make_session(
        db,
        seeded,
        session_metadata={"active_skill": "write-prd", "active_skill_phase": "intake"},
    )
    stub = _scripted_stream([_result(tool_calls=[_AWAIT_REVIEW_CALL])])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "here is all the context you need")
    return session, events


async def test_await_review_pauses_session_with_deliverable(db, seeded, kv, monkeypatch):
    session, events = await _pause_on_deliverable(db, seeded, kv, monkeypatch)

    # Tool runs, then the pause event ends the turn — no DoneEvent.
    assert [type(e) for e in events] == [
        ToolStartEvent,
        ToolResultEvent,
        AwaitingReviewEvent,
    ]
    pause = events[-1]
    assert pause.kind == "deliverable"
    assert pause.deliverable_kind == "prd"
    assert pause.summary_for_user == "Drafted the PRD."
    assert pause.pending_action is None

    await db.refresh(session)
    assert session.status == "awaiting_review"
    assert session.session_metadata["pending_deliverable"] == {
        "deliverable_kind": "prd",
        "document_id": None,
        "summary_for_user": "Drafted the PRD.",
        "url": None,
    }
    # Usage from the paused turn still lands on the session.
    assert session.total_input_tokens == 10


async def test_await_review_without_active_skill_does_not_pause(
    db, seeded, kv, monkeypatch
):
    """Spurious AwaitReview in casual chat (no active skill) must not trap the
    user in the approval bar — the loop just continues."""
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        [_result(tool_calls=[_AWAIT_REVIEW_CALL])],
        [_result(text="anyway, as I was saying")],
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "hello")

    assert not any(isinstance(e, AwaitingReviewEvent) for e in events)
    assert isinstance(events[-1], DoneEvent)
    await db.refresh(session)
    assert session.status == "active"


async def test_approve_resolves_deliverable_and_resumes(db, seeded, kv, monkeypatch):
    session, _ = await _pause_on_deliverable(db, seeded, kv, monkeypatch)

    stub = _scripted_stream([StreamChunk(text="Great!"), _result(text="Great!")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "/approve")

    assert isinstance(events[-1], DoneEvent)
    await db.refresh(session)
    assert session.status == "active"
    assert "active_skill" not in session.session_metadata
    assert "pending_deliverable" not in session.session_metadata

    # The model got the synthetic resume note as a trailing system message.
    sent = stub.calls[0]["messages"]
    assert sent[-1]["role"] == "system"
    assert "approved the deliverable" in sent[-1]["content"]
    # The note is synthetic — it must NOT be persisted as a message.
    roles = [m.role for m in await _messages_for(db, session.id)]
    assert roles.count("user") == 2  # the context message + "/approve"


async def test_revise_keeps_skill_active_and_carries_detail(db, seeded, kv, monkeypatch):
    session, _ = await _pause_on_deliverable(db, seeded, kv, monkeypatch)

    stub = _scripted_stream([_result(text="On it.")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    await _run_turn(db, kv, session.id, "/revise add a non-goals section")

    await db.refresh(session)
    assert session.status == "active"
    assert session.session_metadata.get("active_skill") == "write-prd"
    assert "pending_deliverable" not in session.session_metadata
    note = stub.calls[0]["messages"][-1]
    assert note["role"] == "system"
    assert "add a non-goals section" in note["content"]


async def test_restart_clears_skill_state(db, seeded, kv, monkeypatch):
    session, _ = await _pause_on_deliverable(db, seeded, kv, monkeypatch)

    stub = _scripted_stream([_result(text="Fresh start.")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    await _run_turn(db, kv, session.id, "/restart")

    await db.refresh(session)
    assert session.status == "active"
    assert "active_skill" not in session.session_metadata
    assert "pending_deliverable" not in session.session_metadata


async def test_free_text_reply_leaves_pause_in_place(db, seeded, kv, monkeypatch):
    """Current behavior (finding A6, fix scheduled in Phase 1 plan item 8):
    a free-form reply while paused is NOT classified as approve/revise/restart,
    so the pause survives — but a full model turn still runs with the pause
    intact. We pin the state outcome here."""
    session, _ = await _pause_on_deliverable(db, seeded, kv, monkeypatch)

    stub = _scripted_stream([_result(text="sure, let me elaborate")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "hmm what about the timeline?")

    assert isinstance(events[-1], DoneEvent)
    await db.refresh(session)
    assert session.status == "awaiting_review"
    assert "pending_deliverable" in session.session_metadata


async def test_rewrite_staged_tool_result_replaces_pending_marker(db, seeded):
    session = await _make_session(db, seeded)
    stale = Message(
        id=uuid4(),
        session_id=session.id,
        turn_id=1,
        seq=1,
        role="tool",
        content=[
            {
                "type": "tool_result",
                "tool_use_id": "call_x",
                "tool_name": "SendEmail",
                "output": "[Pending approval] Email staged: 'Hi' to a@x.com.",
                "is_error": False,
            }
        ],
    )
    unrelated = Message(
        id=uuid4(),
        session_id=session.id,
        turn_id=1,
        seq=2,
        role="tool",
        content=[
            {
                "type": "tool_result",
                "tool_use_id": "call_y",
                "tool_name": "TimeCheck",
                "output": "it is noon",
                "is_error": False,
            }
        ],
    )
    db.add_all([stale, unrelated])
    await db.commit()

    rewritten = await _rewrite_staged_tool_result(db, session.id, "[STAGED → DONE] sent.")
    await db.commit()
    assert rewritten is True

    refreshed = await _messages_for(db, session.id)
    outputs = [m.content[0]["output"] for m in refreshed]
    assert "[STAGED → DONE] sent." in outputs
    assert "it is noon" in outputs  # untouched
    assert not any("[Pending approval]" in o for o in outputs)

    # Nothing left to rewrite → False.
    assert await _rewrite_staged_tool_result(db, session.id, "again") is False


# ---------- (d) pending-action pause + approve / refusal / revise / restart ----------


_SEND_EMAIL_CALL = ToolCall(
    id="call_send",
    name="SendEmail",
    arguments_json=json.dumps(
        {
            "to": ["alice@example.com"],
            "subject": "Launch update",
            "body_markdown": "We shipped it.",
        }
    ),
)


async def _stage_email(db, seeded, kv, monkeypatch) -> tuple[Session, list]:
    """One turn where the model calls the real SendEmail tool, which stages a
    pending_action and pauses the session."""
    session = await _make_session(db, seeded)
    stub = _scripted_stream([_result(tool_calls=[_SEND_EMAIL_CALL])])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "email alice about the launch")
    return session, events


def _commit_stage_recorder(monkeypatch) -> list[str]:
    """Wrap _safe_commit so tests can assert the commit-stage protocol while
    still really committing."""
    stages: list[str] = []
    real = session_engine._safe_commit

    async def _recording(db, session_id, stage):
        stages.append(stage)
        await real(db, session_id, stage)

    monkeypatch.setattr(session_engine, "_safe_commit", _recording)
    return stages


async def test_send_email_stages_action_and_pauses(db, seeded, kv, monkeypatch):
    session, events = await _stage_email(db, seeded, kv, monkeypatch)

    assert [type(e) for e in events] == [
        ToolStartEvent,
        ToolResultEvent,
        AwaitingReviewEvent,
    ]
    assert "[Pending approval]" in events[1].output

    pause = events[-1]
    assert pause.kind == "send_email"
    assert pause.pending_action["tool_name"] == "SendEmail"
    assert pause.pending_action["preview"]["to"] == ["alice@example.com"]
    assert "alice@example.com" in pause.summary_for_user

    await db.refresh(session)
    assert session.status == "awaiting_review"
    actions = session.session_metadata["pending_actions"]
    assert len(actions) == 1
    assert actions[0]["kind"] == "send_email"
    assert actions[0]["params"]["subject"] == "Launch update"
    # The staging tool_call's id is recorded for targeted result rewriting.
    assert actions[0]["call_id"] == "call_send"

    # The staged tool result is in the DB with the pending marker.
    messages = await _messages_for(db, session.id)
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "[Pending approval]" in tool_msgs[0].content[0]["output"]


async def test_approve_executes_with_two_phase_commit(db, seeded, kv, monkeypatch):
    session, _ = await _stage_email(db, seeded, kv, monkeypatch)

    execute = AsyncMock(return_value="Email sent to alice@example.com: 'Launch update'.")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)
    stages = _commit_stage_recorder(monkeypatch)

    stub = _scripted_stream([StreamChunk(text="Sent!"), _result(text="Sent!")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "/approve")

    execute.assert_awaited_once()
    assert isinstance(events[-1], DoneEvent)

    # Two-phase commit: the 'executing' stamp is committed BEFORE the send,
    # the executed result right after — and both precede this turn's normal
    # persistence commits.
    assert stages.index("mark_action_executing") < stages.index("record_action_executed")
    assert stages.index("record_action_executed") < stages.index("persist_user_message")

    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None

    # The staged "[Pending approval]" tool result was rewritten to a
    # definitive end state so the model can't re-act on a stale pending marker.
    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → APPROVED & EXECUTED]" in tool_msgs[0].content[0]["output"]
    assert "[Pending approval]" not in tool_msgs[0].content[0]["output"]

    # The resume note tells the model the action is complete.
    note = stub.calls[0]["messages"][-1]
    assert note["role"] == "system"
    assert "ACTION COMPLETE" in note["content"]


async def test_reapprove_of_executing_action_refuses_resend(db, seeded, kv, monkeypatch):
    """An action stamped 'executing' means a previous approve crashed between
    the send and the result-commit. Approving again must NOT re-execute."""
    session, _ = await _stage_email(db, seeded, kv, monkeypatch)

    # Simulate the interrupted first approve: stamp committed, then crash.
    session_engine.mark_action_executing(session)
    await db.commit()

    execute = AsyncMock(return_value="should never run")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)

    stub = _scripted_stream([_result(text="Please double-check your Sent folder.")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "/approve")

    execute.assert_not_awaited()
    assert isinstance(events[-1], DoneEvent)

    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → UNKNOWN]" in tool_msgs[0].content[0]["output"]

    note = stub.calls[0]["messages"][-1]
    assert note["role"] == "system"
    assert "interrupted" in note["content"]
    assert "verify" in note["content"].lower()


async def test_approve_failure_clears_pause_and_reports(db, seeded, kv, monkeypatch):
    session, _ = await _stage_email(db, seeded, kv, monkeypatch)

    execute = AsyncMock(side_effect=RuntimeError("Gmail timeout"))
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)

    stub = _scripted_stream([_result(text="Sorry — sending failed.")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "/approve")

    assert isinstance(events[-1], DoneEvent)
    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → FAILED]" in tool_msgs[0].content[0]["output"]
    assert "Gmail timeout" in stub.calls[0]["messages"][-1]["content"]


async def test_revise_clears_staged_action_without_sending(db, seeded, kv, monkeypatch):
    session, _ = await _stage_email(db, seeded, kv, monkeypatch)

    execute = AsyncMock(return_value="should never run")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)

    stub = _scripted_stream([_result(text="Re-drafting now.")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    await _run_turn(db, kv, session.id, "/revise make the tone warmer")

    execute.assert_not_awaited()
    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → REVISED]" in tool_msgs[0].content[0]["output"]

    note = stub.calls[0]["messages"][-1]
    assert "make the tone warmer" in note["content"]
    assert "SendEmail" in note["content"]  # instructs the model to re-stage


async def test_restart_cancels_staged_action(db, seeded, kv, monkeypatch):
    session, _ = await _stage_email(db, seeded, kv, monkeypatch)

    execute = AsyncMock(return_value="should never run")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)

    stub = _scripted_stream([_result(text="Cancelled.")])
    monkeypatch.setattr(session_engine, "stream_message", stub)
    await _run_turn(db, kv, session.id, "cancel")

    execute.assert_not_awaited()
    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → CANCELLED]" in tool_msgs[0].content[0]["output"]


# ---------- (d2) multiple staged actions + paused-turn guardrails ----------


_SEND_EMAIL_CALL_2 = ToolCall(
    id="call_send_2",
    name="SendEmail",
    arguments_json=json.dumps(
        {
            "to": ["bob@example.com"],
            "subject": "Retro notes",
            "body_markdown": "Notes attached.",
        }
    ),
)


async def test_two_staged_actions_pause_once_per_action(db, seeded, kv, monkeypatch):
    """Finding A4: two SendEmail calls in one batch must BOTH stage (the old
    singular slot silently dropped one). The session pauses on the first;
    approving it executes it, rewrites only ITS tool result (call_id match),
    and re-pauses on the second; approving that resumes a model turn carrying
    both outcome notes."""
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        [_result(tool_calls=[_SEND_EMAIL_CALL, _SEND_EMAIL_CALL_2])]
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)
    events = await _run_turn(db, kv, session.id, "email alice and bob")

    pause = events[-1]
    assert isinstance(pause, AwaitingReviewEvent)
    assert pause.pending_action["preview"]["to"] == ["alice@example.com"]

    await db.refresh(session)
    actions = session.session_metadata["pending_actions"]
    assert [a["call_id"] for a in actions] == ["call_send", "call_send_2"]

    # Approve #1: executes it, re-pauses on #2 — NO model call, no DoneEvent.
    execute = AsyncMock(return_value="Email sent to alice@example.com.")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)
    stub2 = _scripted_stream()  # blows up if the model were called
    monkeypatch.setattr(session_engine, "stream_message", stub2)
    events2 = await _run_turn(db, kv, session.id, "/approve")

    execute.assert_awaited_once()
    assert stub2.calls == []
    pause2 = events2[-1]
    assert isinstance(pause2, AwaitingReviewEvent)
    assert pause2.pending_action["preview"]["to"] == ["bob@example.com"]
    assert not any(isinstance(e, DoneEvent) for e in events2)

    await db.refresh(session)
    assert session.status == "awaiting_review"

    # Only the FIRST action's tool result was rewritten (call_id match) —
    # the second is still pending.
    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    outputs = {m.content[0]["tool_use_id"]: m.content[0]["output"] for m in tool_msgs}
    assert "[STAGED → APPROVED & EXECUTED]" in outputs["call_send"]
    assert "[Pending approval]" in outputs["call_send_2"]

    # Approve #2: executes, resumes a model turn carrying BOTH outcome notes
    # (the first one was parked in queued_resume_notes while we re-paused).
    execute2 = AsyncMock(return_value="Email sent to bob@example.com.")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute2)
    stub3 = _scripted_stream(
        [StreamChunk(text="Both sent."), _result(text="Both sent.")]
    )
    monkeypatch.setattr(session_engine, "stream_message", stub3)
    events3 = await _run_turn(db, kv, session.id, "/approve")

    execute2.assert_awaited_once()
    assert isinstance(events3[-1], DoneEvent)
    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None
    assert "queued_resume_notes" not in session.session_metadata

    note = stub3.calls[0]["messages"][-1]
    assert note["role"] == "system"
    assert "alice@example.com" in note["content"]
    assert "bob@example.com" in note["content"]

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    outputs = {m.content[0]["tool_use_id"]: m.content[0]["output"] for m in tool_msgs}
    assert "[STAGED → APPROVED & EXECUTED]" in outputs["call_send_2"]


async def test_free_text_during_staged_action_short_circuits(
    db, seeded, kv, monkeypatch
):
    """Finding A6: with a staged side effect, a free-text reply must NOT run
    a model turn (which could restage or fire send-side tools). The engine
    raises ApprovalPendingError before persisting anything; the pause and the
    staged action survive untouched."""
    session, _ = await _stage_email(db, seeded, kv, monkeypatch)
    stub = _scripted_stream()  # blows up if the model were called
    monkeypatch.setattr(session_engine, "stream_message", stub)
    execute = AsyncMock(return_value="should never run")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)

    before = len(await _messages_for(db, session.id))
    with pytest.raises(session_engine.ApprovalPendingError):
        await _run_turn(db, kv, session.id, "actually can you also cc carol?")

    execute.assert_not_awaited()
    assert stub.calls == []
    # Nothing persisted; pause intact.
    assert len(await _messages_for(db, session.id)) == before
    await db.refresh(session)
    assert session.status == "awaiting_review"
    assert session_engine.get_pending_action(session) is not None


async def test_legacy_singular_pending_action_still_resolves(
    db, seeded, kv, monkeypatch
):
    """Sessions paused before the Phase 1 list migration carry the singular
    `pending_action` key — approve (incl. the lenient phrasing) must still
    find, execute, and clear it."""
    session = await _make_session(
        db,
        seeded,
        status="awaiting_review",
        session_metadata={
            "pending_action": {
                "kind": "send_email",
                "tool_name": "SendEmail",
                "params": {"to": ["a@x.com"], "subject": "Hi", "body_markdown": "B"},
                "preview": {"to": ["a@x.com"], "subject": "Hi", "body_snippet": "B"},
                "staged_at": "2026-01-01T00:00:00+00:00",
            }
        },
    )
    execute = AsyncMock(return_value="Email sent to a@x.com.")
    monkeypatch.setattr(session_engine, "execute_pending_action", execute)
    stub = _scripted_stream([_result(text="Sent!")])
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "yes, send it!")

    execute.assert_awaited_once()
    assert isinstance(events[-1], DoneEvent)
    await db.refresh(session)
    assert session.status == "active"
    assert session_engine.get_pending_action(session) is None
    assert "pending_action" not in session.session_metadata


# ---------- (e) cancel mid-stream ----------


async def test_cancel_mid_stream_persists_partial_text_with_marker(
    db, seeded, kv, monkeypatch
):
    """Phase 1 cancel semantics (plan item 6): the chunk that observes the
    flag is dropped, the provider stream is closed, and the partial assistant
    text IS persisted with an interruption marker so a reload doesn't lose
    what the user saw. A DoneEvent with cancelled=True closes the turn."""
    session = await _make_session(db, seeded)
    stream_closed = {"value": False}

    async def _stub(messages, model=None, tools=None, api_key=None):
        try:
            yield StreamChunk(text="partial ")
            await kv.set(_cancel_key(session.id), "1", ex=60)
            yield StreamChunk(text="answer")
            yield _result(text="partial answer", input_tokens=99, output_tokens=99)
        finally:
            stream_closed["value"] = True

    monkeypatch.setattr(session_engine, "stream_message", _stub)

    events = await _run_turn(db, kv, session.id, "long question")

    # Only the pre-cancel delta was yielded; no text after the cancel.
    assert [type(e) for e in events] == [TextEvent, DoneEvent]
    assert events[0].text == "partial "
    done = events[-1]
    assert done.cancelled is True
    # The StreamResult was never received (cancel broke out first), so this
    # turn's usage is genuinely unknown — zero, not 99.
    assert done.input_tokens == 0 and done.output_tokens == 0

    # The provider stream was explicitly closed, not abandoned.
    assert stream_closed["value"] is True

    # User message AND the partial assistant text persisted, with a marker.
    messages = await _messages_for(db, session.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    text = messages[1].content[0]["text"]
    assert text.startswith("partial ")
    assert "interrupted" in text.lower()

    # The cancel key is cleaned up at the end of the turn.
    assert not await kv.exists(_cancel_key(session.id))


async def test_cancel_records_usage_when_stream_result_already_received(
    db, seeded, kv, monkeypatch, echo_tool
):
    """Cancel observed at the top of the next loop iteration (set while the
    batch's tools ran): the completed iteration's StreamResult usage/cost is
    recorded, not discarded (finding A10)."""
    session = await _make_session(db, seeded)

    async def _cancelling_handler(args: dict) -> str:
        await kv.set(_cancel_key(session.id), "1", ex=60)
        return "done"

    monkeypatch.setattr(echo_tool, "handler", _cancelling_handler)
    stub = _scripted_stream(
        [
            _result(
                tool_calls=[
                    ToolCall(id="c1", name="TestEcho", arguments_json="{}")
                ],
                input_tokens=25,
                output_tokens=5,
                cost_usd=Decimal("0.004"),
            )
        ],
        # Scripted second iteration must never run — cancel breaks first.
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "go")

    # One model call only; the cancel was seen before the second.
    assert len(stub.calls) == 1
    done = events[-1]
    assert isinstance(done, DoneEvent)
    assert done.cancelled is True
    assert done.input_tokens == 25
    assert done.cost_usd == Decimal("0.004")
    await db.refresh(session)
    assert session.total_input_tokens == 25


async def test_cancel_before_tool_execution_skips_but_pairs_results(
    db, seeded, kv, monkeypatch, echo_tool
):
    """Cancel observed before a tool in the batch runs: the tool is skipped,
    but a synthetic '[Cancelled]' tool_result is still emitted AND persisted
    for it — a tool_use without a paired tool_result would make the rebuilt
    provider history invalid forever."""
    session = await _make_session(db, seeded)
    ran: list[str] = []

    async def _first_handler(args: dict) -> str:
        ran.append(args["value"])
        # Simulate the user pressing Stop while tool #1 runs.
        await kv.set(_cancel_key(session.id), "1", ex=60)
        return "first done"

    monkeypatch.setattr(echo_tool, "handler", _first_handler)
    stub = _scripted_stream(
        [
            _result(
                tool_calls=[
                    ToolCall(id="c1", name="TestEcho", arguments_json='{"value": "one"}'),
                    ToolCall(id="c2", name="TestEcho", arguments_json='{"value": "two"}'),
                ]
            )
        ],
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    events = await _run_turn(db, kv, session.id, "run both")

    # Tool #1 ran; tool #2 was skipped.
    assert ran == ["one"]
    results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert [r.call_id for r in results] == ["c1", "c2"]
    assert results[0].output == "first done"
    assert results[1].is_error is True
    assert "[Cancelled]" in results[1].output
    assert isinstance(events[-1], DoneEvent)
    assert events[-1].cancelled is True

    # Both tool_results persisted — pairing with the tool_use blocks intact.
    messages = await _messages_for(db, session.id)
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert [m.content[0]["tool_use_id"] for m in tool_msgs] == ["c1", "c2"]
    assert "[Cancelled]" in tool_msgs[1].content[0]["output"]


async def test_cancel_discards_action_staged_earlier_in_batch(
    db, seeded, kv, monkeypatch
):
    """A SendEmail staged before the user hit Stop must not survive the
    cancel as a dangling pending_action — and its '[Pending approval]' tool
    result is rewritten to a definitive cancelled state."""
    session = await _make_session(db, seeded)

    stub = _scripted_stream([_result(tool_calls=[_SEND_EMAIL_CALL])])
    monkeypatch.setattr(session_engine, "stream_message", stub)

    # Stage via the real SendEmail tool, then cancel before the pause check.
    real_execute = session_engine.execute_tool

    async def _execute_then_cancel(name, args):
        output = await real_execute(name, args)
        await kv.set(_cancel_key(session.id), "1", ex=60)
        return output

    monkeypatch.setattr(session_engine, "execute_tool", _execute_then_cancel)

    events = await _run_turn(db, kv, session.id, "email alice")

    # No pause — the turn ends cancelled instead.
    assert not any(isinstance(e, AwaitingReviewEvent) for e in events)
    assert isinstance(events[-1], DoneEvent) and events[-1].cancelled is True

    await db.refresh(session)
    assert session.status == "active"
    assert not session_engine.get_pending_action(session)

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → CANCELLED]" in tool_msgs[0].content[0]["output"]
    assert "[Pending approval]" not in tool_msgs[0].content[0]["output"]


async def test_cleanup_runs_on_provider_exception(db, seeded, kv, monkeypatch):
    """finding A9: the tool contextvar and the cancel key must be cleaned up
    even when the provider stream raises mid-turn."""
    from app.core.tools import _current_context

    session = await _make_session(db, seeded)

    async def _exploding(messages, model=None, tools=None, api_key=None):
        if False:  # pragma: no cover — async generator marker
            yield
        raise RuntimeError("provider down")

    monkeypatch.setattr(session_engine, "stream_message", _exploding)
    # A stale cancel flag from a previous stop attempt.
    await kv.set(_cancel_key(session.id), "1", ex=60)

    with pytest.raises(RuntimeError, match="provider down"):
        await _run_turn(db, kv, session.id, "boom")

    assert _current_context.get() is None  # contextvar reset
    assert not await kv.exists(_cancel_key(session.id))  # cancel key deleted


# ---------- (e2) per-session serialization ----------


async def test_concurrent_turns_for_one_session_serialize(
    db, seeded, kv, monkeypatch, test_engine
):
    """Belt-and-braces lock (finding A3): two concurrent process_message
    calls for the same session must run one after the other — interleaving
    would corrupt turn_count and seq."""
    from sqlalchemy.ext.asyncio import AsyncSession as SA_AsyncSession

    session = await _make_session(db, seeded)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def _stub(messages, model=None, tools=None, api_key=None):
        if not first_started.is_set():
            first_started.set()
            order.append("first:start")
            await release_first.wait()
            order.append("first:end")
            yield _result(text="one")
        else:
            order.append("second:start")
            yield _result(text="two")

    monkeypatch.setattr(session_engine, "stream_message", _stub)

    async def _turn(label: str):
        # Each concurrent turn needs its own DB session, like real WS tasks.
        async with SA_AsyncSession(test_engine, expire_on_commit=False) as turn_db:
            return await _run_turn(turn_db, kv, session.id, label)

    t1 = asyncio.create_task(_turn("first"))
    await first_started.wait()
    t2 = asyncio.create_task(_turn("second"))
    # Give t2 a chance to (incorrectly) start streaming while t1 is parked.
    await asyncio.sleep(0.05)
    assert "second:start" not in order
    release_first.set()
    await asyncio.gather(t1, t2)

    assert order == ["first:start", "first:end", "second:start"]

    # turn_count advanced exactly twice; seq strictly monotonic.
    await db.refresh(session)
    assert session.turn_count == 2
    messages = await _messages_for(db, session.id)
    seqs = [m.seq for m in messages]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


# ---------- (f) commit failure ----------


async def test_commit_failure_raises_commit_failed_error_with_stage(
    db, seeded, kv, monkeypatch
):
    session = await _make_session(db, seeded)
    stub = _scripted_stream([_result(text="never reached")])
    monkeypatch.setattr(session_engine, "stream_message", stub)

    real_commit = db.commit
    state = {"failed": False}

    async def _failing_commit():
        if not state["failed"]:
            state["failed"] = True
            raise RuntimeError("disk full")
        await real_commit()

    monkeypatch.setattr(db, "commit", _failing_commit)

    with pytest.raises(CommitFailedError) as excinfo:
        await _run_turn(db, kv, session.id, "hello")

    # The first turn-scoped commit is the user-message persist.
    assert excinfo.value.stage == "persist_user_message"
    assert isinstance(excinfo.value.original, RuntimeError)
    # The model was never called — the turn died before streaming.
    assert stub.calls == []


# ---------- (g) _history_to_llm_messages ----------


def _msg(role: str, content: list) -> SimpleNamespace:
    return SimpleNamespace(role=role, content=content)


def test_history_translates_user_and_assistant_text():
    history = [
        _msg("user", [{"type": "text", "text": "hi"}]),
        _msg("assistant", [{"type": "text", "text": "hello"}]),
    ]
    assert _history_to_llm_messages(history) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_history_drops_empty_user_message():
    history = [
        _msg("user", [{"type": "text", "text": "   "}]),
        _msg("assistant", [{"type": "text", "text": "still here"}]),
    ]
    out = _history_to_llm_messages(history)
    assert [m["role"] for m in out] == ["assistant"]


def test_history_pairs_tool_use_and_tool_result_across_turns():
    history = [
        _msg("user", [{"type": "text", "text": "what time is it"}]),
        _msg(
            "assistant",
            [
                {"type": "text", "text": "checking"},
                {"type": "tool_use", "id": "c1", "name": "TimeCheck", "input": {"tz": "UTC"}},
            ],
        ),
        _msg(
            "tool",
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "c1",
                    "tool_name": "TimeCheck",
                    "output": "noon",
                    "is_error": False,
                }
            ],
        ),
        _msg("assistant", [{"type": "text", "text": "it is noon"}]),
        _msg("user", [{"type": "text", "text": "thanks"}]),
    ]
    out = _history_to_llm_messages(history)
    assert [m["role"] for m in out] == ["user", "assistant", "tool", "assistant", "user"]
    assistant = out[1]
    assert assistant["content"] == "checking"
    assert assistant["tool_calls"] == [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "TimeCheck", "arguments": json.dumps({"tz": "UTC"})},
        }
    ]
    assert out[2] == {"role": "tool", "tool_call_id": "c1", "content": "noon"}


def test_history_assistant_tool_only_message_has_null_content():
    history = [
        _msg(
            "assistant",
            [{"type": "tool_use", "id": "c2", "name": "T", "input": {}}],
        )
    ]
    out = _history_to_llm_messages(history)
    assert out[0]["content"] is None
    assert len(out[0]["tool_calls"]) == 1


def test_history_ignores_non_dict_and_unknown_blocks():
    history = [
        _msg("user", ["raw-string-block", {"type": "text", "text": "real"}]),
        _msg("tool", [{"type": "something_else"}, "junk"]),
    ]
    out = _history_to_llm_messages(history)
    assert out == [{"role": "user", "content": "real"}]


# ---------- (h) MAX_TOOL_ITERATIONS exhaustion ----------


async def test_tool_loop_stops_at_max_iterations_then_wraps_up(
    db, seeded, kv, monkeypatch, echo_tool, caplog
):
    """A model that always calls tools is cut off after MAX_TOOL_ITERATIONS.
    Phase 1 item 9 (finding A11): the exhaustion is no longer silent — one
    final model call WITHOUT tools produces a wrap-up for the user, capped at
    exactly one extra call."""
    session = await _make_session(db, seeded)
    counter = {"n": 0}
    tools_seen: list = []

    async def _always_tools(messages, model=None, tools=None, api_key=None):
        counter["n"] += 1
        tools_seen.append(tools)
        if tools is None:
            # The wrap-up call — no tools offered, so the model can only talk.
            yield StreamChunk(text="Ran out of tool budget; here's where we are.")
            yield _result(
                text="Ran out of tool budget; here's where we are.",
                input_tokens=10,
                output_tokens=1,
            )
            return
        yield _result(
            tool_calls=[
                ToolCall(
                    id=f"call_{counter['n']}",
                    name="TestEcho",
                    arguments_json='{"value": "again"}',
                )
            ],
            input_tokens=10,
            output_tokens=1,
        )

    monkeypatch.setattr(session_engine, "stream_message", _always_tools)

    with caplog.at_level("WARNING"):
        events = await _run_turn(db, kv, session.id, "loop forever")

    # MAX tool iterations + exactly one tools=None wrap-up call.
    assert counter["n"] == MAX_TOOL_ITERATIONS + 1
    assert tools_seen[-1] is None
    assert all(t is not None for t in tools_seen[:-1])
    starts = [e for e in events if isinstance(e, ToolStartEvent)]
    assert len(starts) == MAX_TOOL_ITERATIONS
    # The wrap-up text reached the user, and the DoneEvent closes the turn
    # with the wrap-up call's usage included.
    texts = [e for e in events if isinstance(e, TextEvent)]
    assert texts and "tool budget" in texts[-1].text
    assert isinstance(events[-1], DoneEvent)
    assert events[-1].input_tokens == 10 * (MAX_TOOL_ITERATIONS + 1)
    assert any("MAX_TOOL_ITERATIONS" in r.message for r in caplog.records)

    # Every iteration persisted its assistant tool_use + tool result, with
    # strictly increasing seq throughout; the wrap-up text persisted too.
    messages = await _messages_for(db, session.id)
    seqs = [m.seq for m in messages]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert len([m for m in messages if m.role == "tool"]) == MAX_TOOL_ITERATIONS
    assert messages[-1].role == "assistant"
    assert "tool budget" in messages[-1].content[0]["text"]


async def test_wrap_up_failure_still_closes_turn(
    db, seeded, kv, monkeypatch, echo_tool
):
    """The wrap-up call is best-effort: a provider error there must not
    destroy the already-committed tool work — the turn still gets a
    DoneEvent."""
    session = await _make_session(db, seeded)

    async def _tools_then_crash(messages, model=None, tools=None, api_key=None):
        if tools is None:
            raise RuntimeError("provider down")
        yield _result(
            tool_calls=[
                ToolCall(id="c1", name="TestEcho", arguments_json='{"value": "x"}')
            ]
        )

    monkeypatch.setattr(session_engine, "stream_message", _tools_then_crash)

    events = await _run_turn(db, kv, session.id, "loop forever")

    assert isinstance(events[-1], DoneEvent)
    messages = await _messages_for(db, session.id)
    assert len([m for m in messages if m.role == "tool"]) == MAX_TOOL_ITERATIONS


# ---------- (i) context-window management (Phase 1 item 10) ----------


def _hist_msg(turn_id: int, seq: int, role: str, text: str, estimate: int | None):
    return Message(
        id=uuid4(),
        session_id=uuid4(),  # unit tests below never touch the DB
        turn_id=turn_id,
        seq=seq,
        role=role,
        content=[{"type": "text", "text": text}],
        token_count_estimate=estimate,
    )


def test_truncation_drops_whole_oldest_turns():
    history = [
        _hist_msg(1, 1, "user", "q1", 100),
        _hist_msg(1, 2, "assistant", "a1", 100),
        _hist_msg(2, 3, "user", "q2", 100),
        _hist_msg(2, 4, "assistant", "a2", 100),
        _hist_msg(3, 5, "user", "q3", 100),
        _hist_msg(3, 6, "assistant", "a3", 100),
    ]
    kept, omitted = session_engine._truncate_history_to_budget(history, 450)
    # 3 turns x 200 tokens = 600 > 450 → exactly the oldest turn goes, whole.
    assert omitted == 1
    assert [m.turn_id for m in kept] == [2, 2, 3, 3]


def test_truncation_keeps_newest_turn_even_over_budget():
    history = [
        _hist_msg(1, 1, "user", "old", 100),
        _hist_msg(2, 2, "user", "huge", 10_000),
    ]
    kept, omitted = session_engine._truncate_history_to_budget(history, 50)
    assert omitted == 1
    assert [m.turn_id for m in kept] == [2]


def test_truncation_noop_under_budget():
    history = [
        _hist_msg(1, 1, "user", "q1", 100),
        _hist_msg(1, 2, "assistant", "a1", 100),
    ]
    kept, omitted = session_engine._truncate_history_to_budget(history, 10_000)
    assert omitted == 0
    assert kept == history


def test_truncation_falls_back_to_content_estimate_for_legacy_rows():
    # Pre-Phase-1 rows have token_count_estimate=None — the window must
    # estimate from content instead of treating them as free.
    big_text = "x" * 400_000  # ~100k tokens at 4 chars/token
    history = [
        _hist_msg(1, 1, "user", big_text, None),
        _hist_msg(2, 2, "user", "small", None),
    ]
    kept, omitted = session_engine._truncate_history_to_budget(history, 1_000)
    assert omitted == 1
    assert [m.turn_id for m in kept] == [2]


async def test_token_estimates_populated_on_persist(db, seeded, kv, monkeypatch):
    session = await _make_session(db, seeded)
    stub = _scripted_stream(
        [
            _result(
                tool_calls=[
                    ToolCall(id="c1", name="TestEcho", arguments_json='{"value": "v"}')
                ]
            ),
        ],
        [StreamChunk(text="done"), _result(text="done")],
    )
    monkeypatch.setattr(session_engine, "stream_message", stub)

    await _run_turn(db, kv, session.id, "estimate me")

    messages = await _messages_for(db, session.id)
    assert len(messages) >= 3  # user + assistant(tool_use) + tool + final text
    for m in messages:
        assert m.token_count_estimate is not None and m.token_count_estimate > 0


async def test_long_history_window_truncates_and_notes(
    db, seeded, kv, monkeypatch, echo_tool
):
    """Six prior turns claiming ~100k tokens each blow any budget: the model
    must receive only the newest turn(s), plus a system note marking the cut,
    and the oldest content must not be sent."""
    session = await _make_session(db, seeded)
    for t in range(1, 7):
        for role, seq_off, text in (("user", 0, f"question {t}"), ("assistant", 1, f"answer {t}")):
            db.add(
                Message(
                    id=uuid4(),
                    session_id=session.id,
                    turn_id=t,
                    seq=t * 2 - 1 + seq_off,
                    role=role,
                    content=[{"type": "text", "text": text}],
                    token_count_estimate=50_000,
                )
            )
    session.turn_count = 6
    await db.commit()

    stub = _scripted_stream([StreamChunk(text="ok"), _result(text="ok")])
    monkeypatch.setattr(session_engine, "stream_message", stub)

    await _run_turn(db, kv, session.id, "and now?")

    sent = stub.calls[0]["messages"]
    system_text = " ".join(
        m.get("content") or "" for m in sent if m.get("role") == "system"
    )
    assert "truncated" in system_text
    all_text = json.dumps(sent)
    assert "answer 6" in all_text  # newest turn survives
    assert "question 1" not in all_text  # oldest turn dropped


async def test_short_history_sends_everything_unnoted(db, seeded, kv, monkeypatch):
    session = await _make_session(db, seeded)
    stub1 = _scripted_stream([StreamChunk(text="hi"), _result(text="hi")])
    monkeypatch.setattr(session_engine, "stream_message", stub1)
    await _run_turn(db, kv, session.id, "first")

    stub2 = _scripted_stream([StreamChunk(text="again"), _result(text="again")])
    monkeypatch.setattr(session_engine, "stream_message", stub2)
    await _run_turn(db, kv, session.id, "second")

    sent = stub2.calls[0]["messages"]
    system_text = " ".join(
        m.get("content") or "" for m in sent if m.get("role") == "system"
    )
    assert "truncated" not in system_text
    assert any("first" in (m.get("content") or "") for m in sent)
