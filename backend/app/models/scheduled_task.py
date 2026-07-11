from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONColumn, TimestampMixin, UTCDateTime, uuid_pk


class ScheduledTask(Base, TimestampMixin):
    """A saved prompt the scheduler fires as a headless chat turn on a
    recurrence (v0.3). `schedule` is a small JSON blob validated by
    app.schemas.scheduled_task.Schedule — presets only, no cron syntax:
    {"kind": "daily"|"weekdays"|"weekly"|"every_n_hours", "time": "HH:MM",
     "weekday": 0-6, "every_hours": 1-24}."""

    __tablename__ = "scheduled_tasks"

    id: Mapped[UUID] = uuid_pk()
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    schedule: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Adam's v0.3 decision: a run missed while the app was closed fires ONCE
    # on the next launch (marked late) instead of silently skipping the day.
    catch_up_missed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
