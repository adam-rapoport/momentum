from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONColumn


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True
    )
    turn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Per-session monotonic ordering counter (assigned by the session engine).
    # created_at can't order messages within a turn — SQLite's CURRENT_TIMESTAMP
    # has 1-second resolution, so a whole tool batch ties. Sort by
    # (turn_id, seq). Nullable only for the column-add migration; every row is
    # backfilled and every new row gets a value.
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[list] = mapped_column(JSONColumn, nullable=False)
    token_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_compacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["Session"] = relationship(back_populates="messages")  # noqa: F821
