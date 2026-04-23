"""Integration — one row per (user, third-party provider) connection.

Sprint 3 Chunk D introduces this for Google Docs. The model is generic so
future providers (Slack, Jira, …) slot in without a schema change. OAuth
tokens are stored encrypted with Fernet — see `app/core/integrations/vault.py`.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_integration_user_provider"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # connected | disconnected | error
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="connected")
    # Fernet-encrypted JSON blob: {"access_token": "...", "refresh_token": "...",
    # "expires_at": "iso8601", "scopes": [...]}.
    encrypted_credentials: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Free-form provider metadata (Google email, display name, workspace id, …).
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
