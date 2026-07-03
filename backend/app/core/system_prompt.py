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
from app.core.integrations.google_oauth import (
    PROVIDER as GOOGLE_PROVIDER,
    enabled_services,
)
from app.core.memory.store import project_memory_dir
from app.core.search import get_active_search_provider
from app.core.skills import get_skill
from app.models import Integration, Project, User

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


def _build_environment_section(user: User, google_email: str | None) -> str:
    tz = ZoneInfo(settings.user_timezone)
    now = datetime.now(tz)
    role = "Product Manager"
    prefs = user.preferences or {}
    if isinstance(prefs, dict) and prefs.get("role"):
        role = str(prefs["role"])
    # No %-d: the glibc-only no-pad flag crashes strftime on Windows (A24).
    date_str = f"{now.strftime('%A, %B')} {now.day}, {now.year}"
    time_str = now.strftime("%I:%M %p %Z").lstrip("0")
    lines = [
        "## Section 11: Environment Context\n",
        f"- Current date: {date_str} ({time_str})",
        f"- User: {user.display_name or user.email}",
    ]
    if google_email:
        # Surface the Google address explicitly so "send me an email" /
        # "put it on my calendar" map to a real address, not a placeholder.
        lines.append(
            f"- User email (use this when the user says 'send me' / 'email me' / "
            f"'put it on my calendar'): {google_email}"
        )
    lines.extend(
        [
            f"- Role: {role}",
            # Stale "Groq + Llama 3.3" claim removed (A25): the actual model
            # is routed per turn across whichever providers are configured.
            "- Platform: Momentum (local desktop app; the model serving "
            "each turn is routed per turn from the user's Settings)",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _build_integrations_section(
    project: Project,
    google_services: list[str],
    search_provider: str | None,
) -> str:
    mem_dir = project_memory_dir(project)
    if google_services:
        google_line = (
            "- **Google Workspace:** "
            + ", ".join(_GOOGLE_SERVICE_DESCRIPTIONS[svc] for svc in google_services)
            + ". Sends and meeting invites go through pause-and-review (the user "
            "approves in the UI before the action fires)."
        )
    else:
        google_line = (
            "- **Google Workspace:** not connected. Tell the user to visit "
            "Settings and connect Google to use Docs / Gmail / Calendar tools."
        )
    # Reflect the ACTUAL search config (A25) — the prompt used to hardcode
    # "Tavily (active)" even with no key, so the model called WebSearch into
    # a guaranteed failure.
    if search_provider:
        search_line = f"- **Web search:** {search_provider.title()} (active)"
    else:
        search_line = (
            "- **Web search:** NOT configured — `WebSearch` will fail. Tell "
            "the user to add a Tavily or Perplexity key in Settings before "
            "relying on it."
        )
    return (
        "## Section 14: Active Integrations\n\n"
        f"{search_line}\n"
        "- **Web fetch:** httpx + trafilatura (active)\n"
        "- **Project management:** `QueryTickets` returns MOCK data only. Real Jira/Linear integration is post-MVP — always flag this to the user.\n"
        f"{google_line}\n"
        "- **Slack / Teams / Discord:** no integration in this build. Use `DraftMessage` for a copy-paste draft.\n"
        f"- **Memory storage:** local filesystem at `{mem_dir}` (markdown files plus a database index).\n"
    )


_GOOGLE_SERVICE_DESCRIPTIONS = {
    "docs": "Docs (`ReadDocument` / `WriteDocument` / `EditDocument` / `ListDocuments`)",
    "gmail": "Gmail (`ListEmails` / `ReadEmail` / `DraftEmail` / `SendEmail`)",
    "calendar": "Calendar (`ListCalendarEvents` / `FindAvailability` / `CreateCalendarEvent`)",
}


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

    # NOTE (A22): we deliberately do NOT claim a "current phase". The old
    # active_skill_phase field was set once at activation and never advanced,
    # so every turn told the model it was in "intake" — actively misleading
    # mid-workflow. The model tracks its own position from the conversation
    # and the workflow body below; we only pin the endpoint.
    phases_str = " → ".join(skill.phases)
    header = (
        "## Section 15: Active Skill\n\n"
        f"You are currently in the **`{skill.name}`** skill workflow.\n\n"
        f"- Phases, in order: {phases_str}. Judge your current phase from "
        "the conversation so far.\n"
        f"- Final phase: **{skill.final_phase}** — call `AwaitReview` here and stop.\n"
        f"- Skill description: {skill.description}\n"
        f"- To exit without completing, the user can type `/cancel-skill`.\n\n"
        "Follow the workflow below. Do NOT jump ahead. Do NOT produce "
        "the final deliverable until the workflow tells you to.\n\n"
        "---\n\n"
    )
    return header + skill.body.strip() + "\n"


async def _load_google_integration(
    db: AsyncSession, user_id: UUID
) -> tuple[str | None, list[str]]:
    """Return (connected Google email, list of enabled service names).
    Used to surface the user's actual address in Section 11 and the live
    Google service list in Section 14."""
    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == GOOGLE_PROVIDER,
        )
    )
    if integration is None or integration.status != "connected":
        return None, []
    google_email = (integration.meta or {}).get("google_email")
    services = enabled_services(integration.scopes or [])
    return google_email, services


async def build_dynamic(
    db: AsyncSession,
    user: User,
    project: Project,
    session_metadata: dict | None = None,
) -> str:
    google_email, google_services = await _load_google_integration(db, user.id)
    search = await get_active_search_provider(db, user.id)
    parts = [
        _build_environment_section(user, google_email),
        _build_project_section(project),
        _build_memory_section(project),
        _build_integrations_section(
            project, google_services, search.name if search else None
        ),
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
