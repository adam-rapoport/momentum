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
    action = session.session_metadata["pending_action"]
    assert action["kind"] == "send_email"
    assert action["params"]["subject"] == "Launch update"

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
    assert "pending_action" not in session.session_metadata

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
    assert "pending_action" not in session.session_metadata

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
    assert "pending_action" not in session.session_metadata

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
    assert "pending_action" not in session.session_metadata

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
    assert "pending_action" not in session.session_metadata

    tool_msgs = [m for m in await _messages_for(db, session.id) if m.role == "tool"]
    assert "[STAGED → CANCELLED]" in tool_msgs[0].content[0]["output"]


# ---------- (e) cancel mid-stream ----------


async def test_cancel_mid_stream_breaks_loop_and_discards_partial_text(
    db, seeded, kv, monkeypatch
):
    """Pin current cancel semantics (Phase 1 plan item 6 will change them):
    the flag is only checked on text chunks; the chunk that observes it is
    dropped, the provider stream is abandoned, the partial assistant text is
    NOT persisted, and the turn's usage/cost are discarded (StreamResult never
    consumed). A DoneEvent with cancelled=True still closes the turn."""
    session = await _make_session(db, seeded)

    async def _stub(messages, model=None, tools=None, api_key=None):
        yield StreamChunk(text="partial ")
        await kv.set(_cancel_key(session.id), "1", ex=60)
        yield StreamChunk(text="answer")
        yield _result(text="partial answer", input_tokens=99, output_tokens=99)

    monkeypatch.setattr(session_engine, "stream_message", _stub)

    events = await _run_turn(db, kv, session.id, "long question")

    # Only the pre-cancel delta was yielded; no text after the cancel.
    assert [type(e) for e in events] == [TextEvent, DoneEvent]
    assert events[0].text == "partial "
    done = events[-1]
    assert done.cancelled is True
    assert done.input_tokens == 0 and done.output_tokens == 0

    # The user message persisted, the partial assistant text did not.
    messages = await _messages_for(db, session.id)
    assert [m.role for m in messages] == ["user"]

    # The cancel key is cleaned up at the end of the turn.
    assert not await kv.exists(_cancel_key(session.id))


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


async def test_tool_loop_stops_at_max_iterations(
    db, seeded, kv, monkeypatch, echo_tool, caplog
):
    """A model that always calls tools is cut off after MAX_TOOL_ITERATIONS.
    The DoneEvent still closes the turn — but note (finding A11, Phase 1 plan
    item 9): the exhaustion is silent to the user, no explanatory text."""
    session = await _make_session(db, seeded)
    counter = {"n": 0}

    async def _always_tools(messages, model=None, tools=None, api_key=None):
        counter["n"] += 1
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

    assert counter["n"] == MAX_TOOL_ITERATIONS
    starts = [e for e in events if isinstance(e, ToolStartEvent)]
    assert len(starts) == MAX_TOOL_ITERATIONS
    assert isinstance(events[-1], DoneEvent)
    assert events[-1].input_tokens == 10 * MAX_TOOL_ITERATIONS
    assert any("MAX_TOOL_ITERATIONS" in r.message for r in caplog.records)

    # Every iteration persisted its assistant tool_use + tool result, with
    # strictly increasing seq throughout.
    messages = await _messages_for(db, session.id)
    seqs = [m.seq for m in messages]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert len([m for m in messages if m.role == "tool"]) == MAX_TOOL_ITERATIONS
