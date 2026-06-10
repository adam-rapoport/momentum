from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, TypeDecorator, Uuid, func
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


class UTCDateTime(TypeDecorator):
    """DateTime that always reads back timezone-aware UTC (finding P6).

    SQLite has no real timezone-aware storage: values come back naive even
    from a DateTime(timezone=True) column, so Pydantic serialized them
    without an offset and the frontend parsed them as LOCAL time. All our
    timestamps are UTC by convention (CURRENT_TIMESTAMP defaults, explicit
    datetime.now(timezone.utc) writes) — this decorator makes that explicit:
    aware values are normalized to naive UTC on write (what SQLite stores
    anyway), and UTC tzinfo is attached on read, so Pydantic emits
    UTC-offset ISO strings ("...Z"). On Postgres (legacy dev DBs) the
    underlying timestamptz already round-trips aware values; the read-side
    normalization is a no-op there.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value.tzinfo is None:
            return value
        value = value.astimezone(timezone.utc)
        # SQLite stores a bare string with no offset — hand it naive UTC so
        # what's stored matches the CURRENT_TIMESTAMP defaults. Postgres
        # timestamptz handles aware values natively.
        if dialect.name == "sqlite":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def uuid_pk() -> Mapped[UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
