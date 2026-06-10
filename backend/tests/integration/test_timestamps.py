"""Timezone-aware timestamps on read (Phase 3 item 21, finding P6).

SQLite hands naive datetimes back; UTCDateTime attaches the UTC tzinfo so
Pydantic emits UTC-offset ISO strings instead of offsetless ones the
frontend would parse as local time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import Session
from app.schemas.session import SessionRead

pytestmark = pytest.mark.asyncio


async def test_server_default_timestamps_read_back_utc_aware(db, seeded):
    user = seeded["user"]
    await db.refresh(user)  # load the server_default-generated timestamps
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset().total_seconds() == 0


async def test_session_read_serializes_with_utc_offset(db, seeded):
    session = Session(
        id=uuid4(),
        user_id=seeded["user"].id,
        project_id=seeded["project"].id,
        title="tz check",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    payload = SessionRead.model_validate(session).model_dump_json()
    # Pydantic emits "Z" for aware-UTC datetimes; either form carries the
    # offset the frontend needs.
    assert '"created_at":"' in payload
    created = SessionRead.model_validate(session).created_at
    assert created.tzinfo is not None
    iso = created.isoformat()
    assert iso.endswith("+00:00") or iso.endswith("Z")


async def test_aware_writes_round_trip_unchanged(db, seeded):
    # An explicit aware write (the app uses datetime.now(timezone.utc) in
    # credentials/oauth paths) must read back as the same instant, aware.
    written = datetime(2026, 6, 10, 12, 30, 45, tzinfo=timezone.utc)
    session = Session(
        id=uuid4(),
        user_id=seeded["user"].id,
        project_id=seeded["project"].id,
        created_at=written,
        updated_at=written,
    )
    db.add(session)
    await db.commit()
    db.expire(session)
    await db.refresh(session)
    assert session.created_at == written
