"""Idempotent default single-user setup (organization + user + project).

The desktop build has no manual seed step, so the app creates this default
workspace on first launch (see the lifespan in app.main). `scripts/seed.py`
also delegates here, so there's a single source of truth for what "seeded"
means. Every step is a no-op when the row already exists, so it's safe to run
on every startup.
"""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.default_user import DEFAULT_PROJECT_SLUG, DEFAULT_USER_EMAIL
from app.models import Organization, Project, User


async def ensure_default_setup(db: AsyncSession) -> None:
    """Create the default org, user, and project if they don't already exist."""
    org = await db.scalar(select(Organization).where(Organization.slug == "adam"))
    if org is None:
        org = Organization(
            id=uuid4(),
            name="Adam's Workspace",
            slug="adam",
            plan="free",
            settings={},
            llm_api_keys={},
        )
        db.add(org)
        await db.flush()

    user = await db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
    if user is None:
        user = User(
            id=uuid4(),
            email=DEFAULT_USER_EMAIL,
            display_name="Adam",
            auth_provider="local",
            auth_provider_id="local-adam",
            organization_id=org.id,
            role="owner",
            preferences={"timezone": "America/Los_Angeles"},
        )
        db.add(user)
        await db.flush()

    project = await db.scalar(
        select(Project).where(
            Project.organization_id == org.id, Project.slug == DEFAULT_PROJECT_SLUG
        )
    )
    if project is None:
        project = Project(
            id=uuid4(),
            organization_id=org.id,
            name="Default",
            slug=DEFAULT_PROJECT_SLUG,
            description="Default project for local dev.",
            project_md=None,
            settings={},
            memory_path=None,
        )
        db.add(project)

    await db.commit()
