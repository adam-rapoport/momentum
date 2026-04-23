from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    project_id: UUID | None = None
    title: str | None = Field(None, max_length=255)


class SessionUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    status: str | None = Field(None, pattern="^(active|paused|completed|archived)$")


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    title: str | None
    permission_mode: str
    llm_provider: str
    llm_model: str
    status: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: Decimal
    turn_count: int
    session_metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MessageBlock(BaseModel):
    type: str
    text: str | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    turn_id: int
    role: str
    content: list[dict]
    created_at: datetime


class SessionDetail(SessionRead):
    messages: list[MessageRead]
