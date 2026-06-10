"""Utility tools: TimeCheck and TodoWrite.

TimeCheck exists because LLMs hallucinate dates — they default to their
training cutoff. Any time the agent needs "today" or "now", it must call
this tool instead of guessing.

TodoWrite is session-scoped: todos live in `sessions.metadata.todos` and
are visible across turns within one session but not across sessions.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.core.tools import Tool, get_context, register
from app.models import Session as SessionModel

_ALLOWED_TODO_STATUS = {"pending", "in_progress", "completed"}


async def _time_check(_input: dict) -> str:
    tz = ZoneInfo(settings.user_timezone)
    now = datetime.now(tz)
    # No %-d / %-I: the glibc-only no-pad flags crash strftime on Windows
    # (finding A24). Compose the unpadded pieces portably instead.
    time_str = now.strftime("%I:%M %p %Z").lstrip("0")
    return f"{now.strftime('%A, %B')} {now.day}, {now.year} {time_str}"


TimeCheck = register(
    Tool(
        name="TimeCheck",
        description=(
            "Returns the current date and time in the user's local timezone. "
            "Always call this instead of guessing 'today' or 'now' — your "
            "training cutoff is not the current date."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=_time_check,
        is_read_only=True,
        is_externally_visible=False,
        category="utility",
    )
)


async def _todo_write(input_data: dict) -> str:
    raw = input_data.get("todos")
    if not isinstance(raw, list):
        return "Error: 'todos' must be a list of {content, status} objects."

    cleaned: list[dict] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            return f"Error: todo #{i + 1} is not an object."
        content = (item.get("content") or "").strip()
        status = (item.get("status") or "pending").strip().lower()
        if not content:
            return f"Error: todo #{i + 1} is missing 'content'."
        if status not in _ALLOWED_TODO_STATUS:
            return (
                f"Error: todo #{i + 1} has invalid status '{status}'. "
                f"Allowed: {sorted(_ALLOWED_TODO_STATUS)}"
            )
        cleaned.append({"content": content, "status": status})

    ctx = get_context()
    session = await ctx.db.scalar(
        select(SessionModel).where(SessionModel.id == ctx.session_id)
    )
    if session is None:
        return f"Error: session {ctx.session_id} not found."

    # Reassign (not in-place mutate) so SQLAlchemy detects the change.
    new_md = dict(session.session_metadata or {})
    new_md["todos"] = cleaned
    session.session_metadata = new_md
    await ctx.db.flush()

    lines = [f"Todos updated ({len(cleaned)} item{'s' if len(cleaned) != 1 else ''}):"]
    icons = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
    for t in cleaned:
        lines.append(f"  {icons[t['status']]} {t['content']}")
    return "\n".join(lines)


TodoWrite = register(
    Tool(
        name="TodoWrite",
        description=(
            "Replace the session's todo list. Use this to plan multi-step work "
            "before you start, and to check off items as you finish them. "
            "Todos live only in the current session. Send the FULL list every "
            "call (partial updates overwrite). Status must be 'pending', "
            "'in_progress', or 'completed' — keep at most one 'in_progress'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Imperative description of the task.",
                            },
                            "status": {
                                "type": "string",
                                "enum": sorted(_ALLOWED_TODO_STATUS),
                            },
                        },
                        "required": ["content", "status"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["todos"],
            "additionalProperties": False,
        },
        handler=_todo_write,
        is_read_only=False,
        is_externally_visible=False,
        category="utility",
    )
)
