from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemoryRecordSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type: str
    title: str
    slug: str
    summary: str | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime


class MemoryRecordDetail(MemoryRecordSummary):
    body: str
    file_path: str
