"""Smoke test: exercise memory store + tools end-to-end without the LLM.

Opens a DB session against the seeded default project, sets a fake tool
context, and walks through save → recall → file inspection.

Usage:
  .venv/bin/python -m scripts.try_memory
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.memory.store import get_memory_root, project_memory_dir
from app.core.tools import (
    ToolContext,
    _load_builtin_tools,
    execute_tool,
    reset_context,
    set_context,
)
from app.dependencies import SessionLocal
from app.models import Project, User

_load_builtin_tools()


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).order_by(User.created_at).limit(1))
        project = await db.scalar(select(Project).order_by(Project.created_at).limit(1))
        if user is None or project is None:
            print("No seeded user/project. Run: .venv/bin/python -m scripts.seed")
            return

        print(f"[try_memory] project: {project.name} (slug={project.slug})")
        print(f"[try_memory] memory root: {get_memory_root()}")
        print(f"[try_memory] project dir: {project_memory_dir(project)}\n")

        ctx = ToolContext(
            db=db, session_id=user.id, project_id=project.id, user_id=user.id
        )
        token = set_context(ctx)
        try:
            print("--- SaveMemory: stakeholder ---")
            out = await execute_tool(
                "SaveMemory",
                {
                    "type": "stakeholder",
                    "title": "Sarah (VP Engineering)",
                    "summary": "VP of Eng; prefers bullet-point weekly updates; scalability-focused",
                    "content": (
                        "## Role\n"
                        "VP of Engineering at Acme Corp. Reports to CEO.\n\n"
                        "## Communication preferences\n"
                        "- Bullet-point weekly updates — no long prose\n"
                        "- Scalability and infra debt are priorities for her\n"
                        "- Prefers written comms over meetings\n"
                    ),
                    "tags": ["engineering", "exec", "vp"],
                },
            )
            print(out, "\n")
            await db.commit()

            print("--- SaveMemory: decision ---")
            out = await execute_tool(
                "SaveMemory",
                {
                    "type": "decision",
                    "title": "Q2 2026 retention goal: 20% lift",
                    "summary": "Targeting 20% lift in day-7 retention by end of Q2 2026",
                    "content": (
                        "## Decision\n"
                        "Day-7 retention target for Q2 2026: +20% over Q1 baseline.\n\n"
                        "## Rationale\n"
                        "Q1 showed retention dipping after onboarding flow changes; "
                        "leadership wants a measurable rebound before Q3 planning.\n\n"
                        "## Decider\n"
                        "Adam, 2026-04-19, agreed with Sarah.\n"
                    ),
                    "tags": ["q2", "retention", "metrics"],
                },
            )
            print(out, "\n")
            await db.commit()

            print("--- RecallMemory (all) ---")
            out = await execute_tool("RecallMemory", {})
            print(out[:1500], "\n…\n")

            print("--- RecallMemory (type=stakeholder) ---")
            out = await execute_tool("RecallMemory", {"type": "stakeholder"})
            print(out[:1500], "\n")

            print("--- RecallMemory (query='sarah') ---")
            out = await execute_tool("RecallMemory", {"query": "sarah"})
            print(out[:800], "\n")

            print("--- MEMORY.md contents ---")
            idx = project_memory_dir(project) / "MEMORY.md"
            if idx.exists():
                print(idx.read_text())
            else:
                print("(no MEMORY.md)")
        finally:
            reset_context(token)


if __name__ == "__main__":
    asyncio.run(main())
