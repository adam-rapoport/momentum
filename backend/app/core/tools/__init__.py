"""Tool registry for the PM agent.

Each tool is a callable the LLM can invoke via the OpenAI-compatible tool-calling
API. Tools register themselves at import time via the `register` helper.
The session engine calls `all_tools()` to get the spec it sends to Groq,
then `execute_tool()` to run a chosen tool.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Request-scoped context passed from the session engine to any tool
    that needs DB access, the current session, or the owning project.

    Set via `set_context()` at the start of each turn; retrieved inside
    a tool handler via `get_context()`.
    """
    db: "AsyncSession"
    session_id: UUID
    project_id: UUID
    user_id: UUID
    # The tool_call id currently being executed — updated by the session
    # engine before each execute_tool call. Lets staging tools (SendEmail,
    # CreateCalendarEvent) record which tool_result belongs to their staged
    # pending_action, so approval can rewrite exactly that result.
    current_call_id: str | None = None


_current_context: ContextVar["ToolContext | None"] = ContextVar(
    "_pmomentum_tool_context", default=None
)


def set_context(ctx: "ToolContext"):
    """Set the tool context for the current async task. Returns a reset token."""
    return _current_context.set(ctx)


def reset_context(token) -> None:
    _current_context.reset(token)


def get_context() -> "ToolContext":
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError(
            "No ToolContext set — this tool requires a DB session. "
            "Tools must be invoked from the session engine."
        )
    return ctx


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict  # JSON Schema for the function's parameters
    handler: Callable[[dict], Awaitable[str]]
    is_read_only: bool = True
    is_externally_visible: bool = False
    category: str = "utility"


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    if tool.name in REGISTRY:
        logger.warning("tool %s already registered; overwriting", tool.name)
    REGISTRY[tool.name] = tool
    return tool


def all_tools() -> list[Tool]:
    return list(REGISTRY.values())


def to_openai_tools(tools: list[Tool] | None = None) -> list[dict]:
    """Format tools for the OpenAI Chat Completions API (which Groq mirrors)."""
    tools = tools if tools is not None else all_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


async def execute_tool(name: str, input_data: dict | str) -> str:
    """Run a tool by name. Always returns a string (what the LLM sees back).

    Errors are converted to strings rather than raised — we want the LLM
    to see the error and potentially recover (e.g., fix its args and retry).
    """
    tool = REGISTRY.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"

    if isinstance(input_data, str):
        try:
            parsed = json.loads(input_data) if input_data.strip() else {}
        except json.JSONDecodeError as e:
            return f"Error: tool '{name}' received invalid JSON arguments: {e}"
    else:
        parsed = input_data

    if not isinstance(parsed, dict):
        parsed = {}

    try:
        return await tool.handler(parsed)
    except Exception as e:  # noqa: BLE001 — deliberate: surface errors to the model
        logger.exception("tool %s failed", name)
        return f"Error executing {name}: {e}"


def _load_builtin_tools() -> None:
    """Import every tool module so each one's `register(...)` call runs."""
    from app.core.tools import (  # noqa: F401
        calendar,
        comms,
        documents,
        gmail,
        memory,
        pm,
        research,
        utility,
    )
