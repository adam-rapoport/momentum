"""Slash-command discovery API — powers the "/" autocomplete menu in the chat
input. Read-only: lists the commands a user can type at the start of a message.

A command is either a *skill* (a multi-phase workflow from the skills registry,
e.g. /write-prd) or a *built-in* (handled by the model router / session engine,
e.g. /deep). The frontend shows these in a popup when the user types "/".
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.skills import load_skills

router = APIRouter(prefix="/commands", tags=["commands"])

# Built-in slash commands that aren't skills. Kept here (not in the skills
# registry) because they're handled elsewhere, but users still discover them
# through the same menu.
_BUILTIN_COMMANDS: list[dict] = [
    {
        "command": "deep",
        "description": "Use the more capable model for one reply.",
        "kind": "builtin",
    },
]


@router.get("")
async def list_commands() -> dict:
    """List every slash command the user can type, built-ins first then skills
    (alphabetical)."""
    skills = load_skills()
    skill_commands = [
        {
            "command": skill.slash_command,
            "description": skill.description,
            "kind": "skill",
        }
        for skill in sorted(skills.values(), key=lambda s: s.slash_command)
    ]
    return {"commands": _BUILTIN_COMMANDS + skill_commands}
