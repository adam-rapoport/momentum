from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Schedule(BaseModel):
    """Preset recurrence — deliberately no cron syntax (non-technical users).
    `time`/`weekday` apply to daily/weekdays/weekly; `every_hours` to
    every_n_hours. Times are the user's local wall clock."""

    kind: Literal["daily", "weekdays", "weekly", "every_n_hours"]
    time: str = "09:00"
    weekday: int = Field(0, ge=0, le=6)  # 0 = Monday
    every_hours: int = Field(6, ge=1, le=24)

    @field_validator("time")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("time must be HH:MM")
        hh, mm = int(parts[0]), int(parts[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("time must be HH:MM")
        return f"{hh:02d}:{mm:02d}"


class ScheduledTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1)
    schedule: Schedule
    enabled: bool = True
    catch_up_missed: bool = True
    project_id: UUID | None = None


class ScheduledTaskUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = Field(None, min_length=1)
    schedule: Schedule | None = None
    enabled: bool | None = None
    catch_up_missed: bool | None = None


class ScheduledTaskRead(BaseModel):
    id: UUID
    name: str
    prompt: str
    schedule: dict
    enabled: bool
    catch_up_missed: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: str | None
    last_session_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
