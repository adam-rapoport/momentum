"""Integration test: session persistence round-trip.

Exercises the Sprint 6 Chunk D fixture machinery end-to-end:
  - test DB is reachable + migrated
  - `seeded` produces a usable Org/User/Project
  - we can write a Session row, commit it, and read it back
  - per-test truncate keeps state isolated

If this passes, the fixture pattern is in place and porting the
manual `try_*.py` smoke scripts (try_pause, try_pause_action,
try_gmail with mocked adapters, etc.) becomes mechanical.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Session

pytestmark = pytest.mark.asyncio


async def test_seeded_fixture_creates_org_user_project(
    db: AsyncSession, seeded: dict
):
    org = seeded["organization"]
    user = seeded["user"]
    project = seeded["project"]

    assert org.id is not None
    assert user.organization_id == org.id
    assert project.organization_id == org.id
    assert user.email == "test@local.dev"
    assert project.slug == "default"


async def test_session_round_trip(db: AsyncSession, seeded: dict):
    """Create a Session row, commit, then re-query in the same db
    fixture and confirm we get our row back with the metadata we set."""
    user = seeded["user"]
    project = seeded["project"]

    session_id = uuid4()
    db.add(
        Session(
            id=session_id,
            user_id=user.id,
            project_id=project.id,
            title="integration smoke",
            session_metadata={"active_skill": "write-prd"},
        )
    )
    await db.commit()

    fetched = await db.scalar(select(Session).where(Session.id == session_id))
    assert fetched is not None
    assert fetched.title == "integration smoke"
    assert fetched.status == "active"
    assert fetched.session_metadata == {"active_skill": "write-prd"}


async def test_message_persists_under_session(
    db: AsyncSession, seeded: dict
):
    user = seeded["user"]
    project = seeded["project"]
    session_id = uuid4()
    db.add(
        Session(
            id=session_id,
            user_id=user.id,
            project_id=project.id,
            title="msg test",
        )
    )
    await db.flush()

    db.add(
        Message(
            id=uuid4(),
            session_id=session_id,
            turn_id=1,
            role="user",
            content=[{"type": "text", "text": "hello"}],
        )
    )
    await db.commit()

    fetched = await db.scalars(
        select(Message).where(Message.session_id == session_id)
    )
    msgs = list(fetched.all())
    assert len(msgs) == 1
    assert msgs[0].role == "user"
    assert msgs[0].content == [{"type": "text", "text": "hello"}]


async def test_session_search_matches_title_and_message_content(
    db: AsyncSession, seeded: dict
):
    """The C4 search expression (title OR CAST(content AS TEXT) ILIKE) must run
    on the test DB (SQLite) and match phrases inside message content, not just
    titles."""
    user = seeded["user"]
    project = seeded["project"]
    s1, s2 = uuid4(), uuid4()
    db.add_all(
        [
            Session(id=s1, user_id=user.id, project_id=project.id, title="Planning doc"),
            Session(id=s2, user_id=user.id, project_id=project.id, title="Misc notes"),
        ]
    )
    await db.flush()
    db.add(
        Message(
            id=uuid4(),
            session_id=s1,
            turn_id=1,
            role="user",
            content=[{"type": "text", "text": "let's discuss the kangaroo roadmap"}],
        )
    )
    await db.commit()

    def search(q: str):
        pattern = f"%{q}%"
        msg_match = select(Message.session_id).where(
            cast(Message.content, Text).ilike(pattern)
        )
        return select(Session).where(
            Session.user_id == user.id,
            or_(Session.title.ilike(pattern), Session.id.in_(msg_match)),
        )

    # Content match, case-insensitive — only s1 has "kangaroo" in a message.
    res = list((await db.scalars(search("KANGAROO"))).all())
    assert [s.id for s in res] == [s1]
    # Title match — only s2.
    res2 = list((await db.scalars(search("misc"))).all())
    assert [s.id for s in res2] == [s2]


async def test_truncate_isolates_tests(db: AsyncSession, seeded: dict):
    """Sanity check: this test relies on the `seeded` fixture re-running
    cleanly even after the previous test inserted Session+Message rows.
    The per-test TRUNCATE in the fixture is what makes this work — if it
    breaks, this test fails because the previous run's data is still
    around and unique constraints on slug/email collide."""
    org = seeded["organization"]
    # If TRUNCATE didn't run, the previous test's "test-org" slug would
    # have already existed and seeded would have hit a unique-violation
    # before reaching us. So just by getting here we've confirmed
    # isolation is working; this assert is a smoke check on top.
    assert org.slug == "test-org"
