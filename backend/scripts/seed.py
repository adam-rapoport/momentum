"""Seed the default single-user setup (organization + user + project).

Idempotent. The actual logic lives in app.core.seed (so the desktop build can
auto-seed on first launch); this script is the manual entry point for local dev:

  .venv/bin/python -m scripts.seed
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.seed import ensure_default_setup
from app.dependencies import SessionLocal, engine


async def seed() -> None:
    async with SessionLocal() as db:
        await ensure_default_setup(db)
    await engine.dispose()
    print("[seed] default workspace ensured (organization 'adam', user adam@local.dev, project 'default').")


if __name__ == "__main__":
    asyncio.run(seed())
