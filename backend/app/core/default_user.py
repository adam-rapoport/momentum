"""Single-user convenience for MVP.

Sprint 1 skips auth, so every request acts as the seeded default user
(adam@local.dev) and the default project (slug="default"). Sprint 4 will
replace this with real JWT auth.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User

DEFAULT_USER_EMAIL = "adam@local.dev"
DEFAULT_PROJECT_SLUG = "default"


async def get_default_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
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
