from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Portable column types so the same models run on SQLite (the desktop default)
# and Postgres:
#   - Uuid(as_uuid=True) -> native UUID on Postgres, CHAR(32) on SQLite.
#   - JSONColumn         -> JSONB on Postgres (matches the existing schema, so
#                           existing Postgres DBs are untouched), plain JSON on
#                           SQLite.
# The app only ever reads/writes these JSON columns as whole blobs (it never
# queries inside them in SQL), so plain JSON on SQLite is functionally identical.
JSONColumn = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def uuid_pk() -> Mapped[UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
