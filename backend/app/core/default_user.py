"""Single-user convenience for the local/desktop build.

There's no login: every request acts as the one seeded local user and the
default project (slug="default"). The user's email and the workspace slug are
just internal identity keys, not personal data.

New installs get neutral values (DEFAULT_*). Older local databases from the
single-developer MVP were seeded with the LEGACY_* values; we keep looking
those up as a fallback so an upgraded install keeps using its real data
instead of spawning a fresh empty workspace.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User

DEFAULT_USER_EMAIL = "you@pmomentum.local"
DEFAULT_ORG_SLUG = "local"
DEFAULT_PROJECT_SLUG = "default"

# Pre-genericization identity. Only used to keep existing local DBs working.
LEGACY_USER_EMAIL = "adam@local.dev"
LEGACY_ORG_SLUG = "adam"


async def get_default_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
    if user is None:  # fall back to a pre-genericization local DB
        user = await db.scalar(select(User).where(User.email == LEGACY_USER_EMAIL))
    if user is None:
        raise RuntimeError(
            "Default user not found. Run `.venv/bin/python -m scripts.seed` first."
        )
    return user


async def get_default_project(db: AsyncSession, organization_id: UUID) -> Project:
    project = await db.scalar(
        select(Project).where(
            Project.organization_id == organization_id,
            Project.slug == DEFAULT_PROJECT_SLUG,
        )
    )
    if project is None:
        raise RuntimeError(
            "Default project not found. Run `.venv/bin/python -m scripts.seed` first."
        )
    return project
