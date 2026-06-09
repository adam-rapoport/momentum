"""Tool registry for the PM agent.

Each tool is a callable the LLM can invoke via the OpenAI-compatible tool-calling
API. Tools register themselves at import time via the `register` helper.
The session engine calls `all_tools()` to get the spec it sends to Groq,
then `execute_tool()` to run a chosen tool.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING
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


# Per-category execution budgets (seconds), applied by execute_tool unless a
# tool sets its own `timeout_seconds`. Categories not listed get the default:
# local-only work (memory/pm/utility/communication/workflow) should never
# take long; network categories get more headroom.
DEFAULT_TOOL_TIMEOUT_SECONDS = 15.0
CATEGORY_TIMEOUT_SECONDS: dict[str, float] = {
    "research": 60.0,   # web search / page fetch
    "gmail": 60.0,      # Google API round-trips
    "calendar": 60.0,   # Google API round-trips
    "documents": 30.0,  # Google Docs / local document ops
}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict  # JSON Schema for the function's parameters
    handler: Callable[[dict], Awaitable[str]]
    is_read_only: bool = True
    is_externally_visible: bool = False
    category: str = "utility"
    # Per-tool override for the execution budget; None -> category default
    # (see CATEGORY_TIMEOUT_SECONDS above).
    timeout_seconds: float | None = None

    @property
    def effective_timeout_seconds(self) -> float:
        if self.timeout_seconds is not None:
            return self.timeout_seconds
        return CATEGORY_TIMEOUT_SECONDS.get(
            self.category, DEFAULT_TOOL_TIMEOUT_SECONDS
        )


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
    Each call runs under a category time budget (finding A23) so one wedged
    Google/network call can't hang the whole turn; a timeout comes back as
    an Error string and the turn keeps going.

    NOTE (Phase 3 candidate): the error protocol is still string-typed —
    callers detect failure via `output.startswith("Error")`. A structured
    (ok, output) result was considered for Phase 1 but deferred to keep the
    diff contained; see plan item 11.
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

    budget = tool.effective_timeout_seconds
    try:
        return await asyncio.wait_for(tool.handler(parsed), timeout=budget)
    except TimeoutError:
        logger.warning("tool %s timed out after %.0fs", name, budget)
        return (
            f"Error: {name} timed out after {budget:.0f}s. The operation was "
            f"aborted; it may be a slow network or service. You can retry or "
            f"proceed without it."
        )
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
