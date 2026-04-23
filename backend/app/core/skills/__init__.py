"""Skill loader and activation detector.

A "skill" is a structured workflow (write-prd, stakeholder-update,
meeting-prep) that steers the agent through a multi-phase process
instead of free-form chatting. Each skill lives in its own directory
under `app/skills/<skill_name>/` with a SKILL.md file that carries
YAML frontmatter (name, slash_command, trigger_keywords, phases, …)
plus the workflow body in markdown.

The body is injected into the system prompt as Section 15 while the
skill is active. Activation is detected here and recorded in
`session.session_metadata.active_skill` by the session engine.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.memory.store import _parse_frontmatter

logger = logging.getLogger(__name__)

# This file lives at app/core/skills/__init__.py; SKILL.md files live at
# app/skills/<name>/SKILL.md (a sibling of `core/`). So walk up three
# levels to reach `app/`, then into `skills/`.
_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
_SLASH_RE = re.compile(r"^/([a-z][a-z0-9-]*)\b", re.IGNORECASE)

CLEAR_SENTINEL = "__CLEAR__"
EXIT_COMMANDS = {"cancel-skill", "exit-skill", "restart"}


@dataclass
class Skill:
    name: str
    description: str
    slash_command: str
    trigger_keywords: list[str]
    required_tools: list[str]
    phases: list[str]
    body: str

    @property
    def first_phase(self) -> str:
        return self.phases[0] if self.phases else "active"

    @property
    def final_phase(self) -> str:
        return self.phases[-1] if self.phases else "active"


_cached_skills: dict[str, Skill] | None = None


def _parse_skill_file(path: Path) -> Skill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("could not read skill file %s: %s", path, e)
        return None

    fm, body = _parse_frontmatter(text)
    name = (fm.get("name") or "").strip()
    if not name:
        logger.warning("skill file %s has no 'name' in frontmatter; skipping", path)
        return None

    def _as_list(key: str) -> list[str]:
        raw = fm.get(key)
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return []

    return Skill(
        name=name,
        description=(fm.get("description") or "").strip(),
        slash_command=(fm.get("slash_command") or name).strip().lower(),
        trigger_keywords=[k.lower() for k in _as_list("trigger_keywords")],
        required_tools=_as_list("required_tools"),
        phases=_as_list("phases"),
        body=body.strip(),
    )


def load_skills(force: bool = False) -> dict[str, Skill]:
    """Load every SKILL.md under app/skills/ into an in-memory registry.

    Cached by default; pass force=True to re-read from disk (useful in dev).
    """
    global _cached_skills
    if _cached_skills is not None and not force:
        return _cached_skills

    registry: dict[str, Skill] = {}
    if not _SKILLS_DIR.exists():
        logger.info("no skills directory at %s", _SKILLS_DIR)
        _cached_skills = registry
        return registry

    for skill_dir in sorted(p for p in _SKILLS_DIR.iterdir() if p.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        skill = _parse_skill_file(skill_file)
        if skill is None:
            continue
        if skill.name in registry:
            logger.warning("duplicate skill name '%s' — overwriting", skill.name)
        registry[skill.name] = skill

    logger.info("loaded %d skill(s): %s", len(registry), sorted(registry))
    _cached_skills = registry
    return registry


def get_skill(name: str | None) -> Skill | None:
    if not name:
        return None
    return load_skills().get(name)


def detect_skill(user_text: str, session_metadata: dict | None) -> str | None:
    """Return the new active_skill state given this user message.

    Rules (first match wins):
      1. Explicit exit (`/cancel-skill`, `/exit-skill`, `/restart`) -> CLEAR_SENTINEL
      2. Slash command at start (`/write-prd ...`) matching a known skill -> skill.name
      3. No skill currently active + user message contains a multi-word
         trigger_keyword -> skill.name
      4. Otherwise -> None (no change to active_skill)

    Returning None means "don't touch whatever's already in session metadata."
    """
    if not user_text:
        return None

    stripped = user_text.strip()
    match = _SLASH_RE.match(stripped)
    if match:
        slug = match.group(1).lower()
        if slug in EXIT_COMMANDS:
            return CLEAR_SENTINEL
        for skill in load_skills().values():
            if skill.slash_command == slug:
                return skill.name

    active = (session_metadata or {}).get("active_skill")
    if active:
        return None

    lowered = stripped.lower()
    for skill in load_skills().values():
        for keyword in skill.trigger_keywords:
            if " " in keyword and keyword in lowered:
                return skill.name
    return None
