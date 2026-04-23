"""Assembles the PM system prompt per turn.

Structure mirrors `PM Agent Architecture.md` Section 3:

  Static half (10 sections)      — loaded once, cached in memory
    + dynamic half (4 sections)  — rebuilt per turn from DB + memory index

The static half is large (~8k tokens). Groq has no prompt caching, so
every turn pays the full input cost — ~$0.005 per turn at Llama 3.3
pricing. Acceptable for local dev; revisit when deploying.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.memory.store import project_memory_dir
from app.core.skills import get_skill
from app.models import Project, User

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "prompts" / "static"
_PROJECT_MD_CAP = 12_000  # chars, per architecture doc
_MEMORY_INDEX_CAP = 25_000  # chars, per architecture doc
_cached_static: str | None = None


def load_static() -> str:
    global _cached_static
    if _cached_static is not None:
        return _cached_static
    files = sorted(_STATIC_DIR.glob("*.md"))
    if not files:
        logger.warning("no static prompt sections found in %s", _STATIC_DIR)
        _cached_static = ""
        return _cached_static
    sections = [p.read_text(encoding="utf-8").strip() for p in files]
    _cached_static = "\n\n".join(sections)
    logger.info(
        "loaded %d static prompt sections (%d chars total)",
        len(sections),
        len(_cached_static),
    )
    return _cached_static


def _build_environment_section(user: User) -> str:
    tz = ZoneInfo(settings.user_timezone)
    now = datetime.now(tz)
    role = "Product Manager"
    prefs = user.preferences or {}
    if isinstance(prefs, dict) and prefs.get("role"):
        role = str(prefs["role"])
    return (
        "## Section 11: Environment Context\n\n"
        f"- Current date: {now.strftime('%A, %B %-d, %Y')} ({now.strftime('%I:%M %p %Z')})\n"
        f"- User: {user.display_name or user.email}\n"
        f"- Role: {role}\n"
        f"- Platform: pMomentum MVP (local dev, Groq + Llama 3.3)\n"
    )


def _build_project_section(project: Project) -> str:
    content = (project.project_md or "").strip()
    if not content:
        content = (
            "_No project context has been provided yet. "
            "When the user shares goals, team structure, or strategic direction, "
            "offer to save them as Product/Team memories so this section becomes richer over time._"
        )
    if len(content) > _PROJECT_MD_CAP:
        content = content[:_PROJECT_MD_CAP].rstrip() + "\n\n…[truncated — project_md exceeds cap]"
    return (
        "## Section 12: Project Context\n\n"
        f"Project: **{project.name}** (slug: `{project.slug}`)\n\n"
        f"{content}\n"
    )


def _build_memory_section(project: Project) -> str:
    index_path = project_memory_dir(project) / "MEMORY.md"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8").strip()
        if len(content) > _MEMORY_INDEX_CAP:
            content = content[:_MEMORY_INDEX_CAP].rstrip() + "\n\n…[truncated]"
    else:
        content = "_No memories saved yet for this project._"
    return (
        "## Section 13: Memory Index\n\n"
        "This is the list of what you already know. Each line is a memory — call "
        "`RecallMemory` (by type + query) or `SearchMemories` (by substring) "
        "to load the full body of any of them.\n\n"
        f"{content}\n"
    )


def _build_integrations_section(project: Project) -> str:
    mem_dir = project_memory_dir(project)
    return (
        "## Section 14: Active Integrations\n\n"
        "- **Web search:** Tavily (active)\n"
        "- **Web fetch:** httpx + trafilatura (active)\n"
        "- **Project management:** `QueryTickets` returns MOCK data only. Real Jira/Linear integration is post-MVP — always flag this to the user.\n"
        "- **Email / Slack:** `DraftMessage` produces drafts only. No send capability exists in this build.\n"
        f"- **Memory storage:** local filesystem at `{mem_dir}` (markdown + Postgres index).\n"
    )


def _build_skill_section(session_metadata: dict | None) -> str | None:
    """Section 15: paste the active skill's workflow body verbatim.

    Returns None when no skill is active, so the section disappears from
    the prompt entirely — we don't want to burden the model with "no skill
    active" noise. When active, the whole SKILL.md body is injected so
    the agent knows the phases and required tools.
    """
    meta = session_metadata or {}
    name = meta.get("active_skill")
    if not name:
        return None
    skill = get_skill(str(name))
    if skill is None:
        logger.warning("session_metadata.active_skill='%s' but skill not registered", name)
        return None

    phase = str(meta.get("active_skill_phase") or skill.first_phase)
    phases_str = " → ".join(f"**{p}**" if p == phase else p for p in skill.phases)
    header = (
        "## Section 15: Active Skill\n\n"
        f"You are currently in the **`{skill.name}`** skill workflow.\n\n"
        f"- Current phase: **{phase}** (of: {phases_str})\n"
        f"- Final phase: **{skill.final_phase}** — call `AwaitReview` here and stop.\n"
        f"- Skill description: {skill.description}\n"
        f"- To exit without completing, the user can type `/cancel-skill`.\n\n"
        "Follow the workflow below. Do NOT jump ahead. Do NOT produce "
        "the final deliverable until the workflow tells you to.\n\n"
        "---\n\n"
    )
    return header + skill.body.strip() + "\n"


async def build_dynamic(
    db: AsyncSession,
    user: User,
    project: Project,
    session_metadata: dict | None = None,
) -> str:
    parts = [
        _build_environment_section(user),
        _build_project_section(project),
        _build_memory_section(project),
        _build_integrations_section(project),
    ]
    skill_section = _build_skill_section(session_metadata)
    if skill_section:
        parts.append(skill_section)
    return "\n\n".join(parts)


async def build_prompt(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    session_metadata: dict | None = None,
) -> str:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise ValueError(f"user {user_id} not found")
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise ValueError(f"project {project_id} not found")

    static = load_static()
    dynamic = await build_dynamic(db, user, project, session_metadata=session_metadata)
    return f"{static}\n\n---\n\n{dynamic}"
