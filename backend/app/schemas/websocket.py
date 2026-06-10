"""Pydantic schemas for the WebSocket protocol.

The outbound models are the frontend contract (pinned byte-for-byte in
tests/integration/test_ws_contract.py): `app.api.websocket` serializes every
outbound frame THROUGH these models (finding A30 — they used to be dead code
that silently drifted from hand-built dicts). Fields may be added but never
removed or renamed.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class InboundMessage(BaseModel):
    type: Literal["session.message"]
    session_id: UUID
    content: str


class InboundCancel(BaseModel):
    type: Literal["session.cancel"]
    session_id: UUID


class OutboundStreamText(BaseModel):
    type: Literal["stream.text"] = "stream.text"
    session_id: UUID
    text: str


class OutboundToolStart(BaseModel):
    type: Literal["stream.tool_start"] = "stream.tool_start"
    session_id: UUID
    call_id: str
    name: str
    input: dict


class OutboundToolResult(BaseModel):
    type: Literal["stream.tool_result"] = "stream.tool_result"
    session_id: UUID
    call_id: str
    name: str
    output: str
    is_error: bool = False


class OutboundAwaitingReview(BaseModel):
    type: Literal["stream.awaiting_review"] = "stream.awaiting_review"
    session_id: UUID
    # 'deliverable' (skill AwaitReview) | 'send_email' | 'create_event'.
    kind: str
    deliverable_kind: str
    document_id: str | None = None
    summary_for_user: str
    url: str | None = None
    model: str | None = None
    # Populated when kind != 'deliverable' — the staged action's preview
    # payload that the ApprovalBar renders.
    pending_action: dict | None = None


class StreamUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    # Decimals cross the wire as strings, not floats.
    cost_usd: str
    total_cost_usd: str


class StreamDoneMetadata(BaseModel):
    cancelled: bool
    model: str | None = None


class OutboundStreamDone(BaseModel):
    type: Literal["stream.done"] = "stream.done"
    session_id: UUID
    usage: StreamUsage
    metadata: StreamDoneMetadata


class OutboundError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    session_id: UUID | None = None
