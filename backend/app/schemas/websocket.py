from decimal import Decimal
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
    deliverable_kind: str
    document_id: str | None = None
    summary_for_user: str
    url: str | None = None


class OutboundStreamDone(BaseModel):
    type: Literal["stream.done"] = "stream.done"
    session_id: UUID
    usage: dict
    metadata: dict


class OutboundError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    session_id: UUID | None = None
