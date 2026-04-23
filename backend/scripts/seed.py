"""Seed the default single-user setup.

Creates (idempotently):
  - Organization "Adam's Workspace" (slug: "adam")
  - User "Adam" (email: adam@local.dev)
  - Project "Default" (slug: "default")

Run with:
  .venv/bin/python -m scripts.seed
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.dependencies import SessionLocal, engine
from app.models import Organization, Project, User


async def seed() -> None:
    async with SessionLocal() as db:
        existing_org = await db.scalar(select(Organization).where(Organization.slug == "adam"))
        if existing_org:
            org = existing_org
            print(f"[seed] organization already exists: {org.name} ({org.id})")
        else:
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
            print(f"[seed] created organization: {org.name} ({org.id})")

        existing_user = await db.scalar(select(User).where(User.email == "adam@local.dev"))
        if existing_user:
            user = existing_user
            print(f"[seed] user already exists: {user.display_name} ({user.id})")
        else:
            user = User(
                id=uuid4(),
                email="adam@local.dev",
                display_name="Adam",
                auth_provider="local",
                auth_provider_id="local-adam",
                organization_id=org.id,
                role="owner",
                preferences={"timezone": "America/Los_Angeles"},
            )
            db.add(user)
            await db.flush()
            print(f"[seed] created user: {user.display_name} ({user.id})")

        existing_project = await db.scalar(
            select(Project).where(
                Project.organization_id == org.id, Project.slug == "default"
            )
        )
        if existing_project:
            project = existing_project
            print(f"[seed] project already exists: {project.name} ({project.id})")
        else:
            project = Project(
                id=uuid4(),
                organization_id=org.id,
                name="Default",
                slug="default",
                description="Default project for local dev.",
                project_md=None,
                settings={},
                memory_path=None,
            )
            db.add(project)
            await db.flush()
            print(f"[seed] created project: {project.name} ({project.id})")

        await db.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
