"""execute_tool error-contract tests (plan item 31 / T-A23).

The session engine detects tool failure via `output.startswith("Error")`
(session_engine.py:782) — these tests pin that contract so a refactor of the
registry can't silently break error propagation to the model.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.tools import (
    DEFAULT_TOOL_TIMEOUT_SECONDS,
    REGISTRY,
    Tool,
    _load_builtin_tools,
    execute_tool,
    get_context,
    register,
)

# The SaveMemory test below needs the real registry populated even when this
# module runs in isolation (normally session_engine's import does this).
_load_builtin_tools()


@pytest.fixture
def failing_tool():
    async def _handler(args: dict) -> str:
        raise RuntimeError("handler exploded")

    tool = register(
        Tool(
            name="TestFailing",
            description="test-only tool that always raises",
            input_schema={"type": "object", "properties": {}},
            handler=_handler,
        )
    )
    yield tool
    REGISTRY.pop("TestFailing", None)


@pytest.fixture
def args_echo_tool():
    async def _handler(args: dict) -> str:
        return f"got:{sorted(args.items())}"

    tool = register(
        Tool(
            name="TestArgsEcho",
            description="test-only tool that echoes parsed args",
            input_schema={"type": "object", "properties": {}},
            handler=_handler,
        )
    )
    yield tool
    REGISTRY.pop("TestArgsEcho", None)


async def test_unknown_tool_returns_error_string():
    out = await execute_tool("NoSuchTool", {})
    assert out.startswith("Error")
    assert "NoSuchTool" in out


async def test_handler_exception_converted_to_error_string(failing_tool):
    out = await execute_tool("TestFailing", {})
    assert out.startswith("Error executing TestFailing")
    assert "handler exploded" in out


async def test_string_args_parsed_as_json(args_echo_tool):
    out = await execute_tool("TestArgsEcho", '{"a": 1}')
    assert out == "got:[('a', 1)]"


async def test_invalid_json_string_args_return_error(args_echo_tool):
    out = await execute_tool("TestArgsEcho", "{not json")
    assert out.startswith("Error")
    assert "invalid JSON" in out


async def test_empty_string_args_become_empty_dict(args_echo_tool):
    assert await execute_tool("TestArgsEcho", "   ") == "got:[]"


async def test_non_dict_json_args_coerced_to_empty_dict(args_echo_tool):
    # A JSON array/scalar isn't a kwargs dict — coerced to {} instead of crashing.
    assert await execute_tool("TestArgsEcho", "[1, 2]") == "got:[]"


async def test_context_requiring_tool_outside_engine_errors_cleanly():
    """Tools that call get_context() outside the engine raise; execute_tool
    converts that to the Error string the model can see. SaveMemory is a
    real registered tool with that dependency."""
    out = await execute_tool(
        "SaveMemory",
        {"type": "decision", "title": "t", "content": "c"},
    )
    assert out.startswith("Error executing SaveMemory")
    assert "ToolContext" in out


def test_get_context_raises_without_engine():
    with pytest.raises(RuntimeError):
        get_context()


async def test_timecheck_formats_portably():
    """Phase 3 item 22 (A24): TimeCheck must not use glibc-only %-d/%-I
    (which crash strftime on Windows) — and the output must still have no
    zero-padded day or hour."""
    import re

    out = await execute_tool("TimeCheck", {})
    assert not out.startswith("Error"), out
    # e.g. "Wednesday, June 10, 2026 3:42 PM PDT"
    m = re.match(
        r"^[A-Z][a-z]+, [A-Z][a-z]+ (\d{1,2}), \d{4} (\d{1,2}):\d{2} [AP]M", out
    )
    assert m, out
    assert not m.group(1).startswith("0")
    assert not m.group(2).startswith("0")


# ---------- per-tool timeouts (Phase 1 item 11, finding A23) ----------


@pytest.fixture
def slow_tool():
    async def _handler(args: dict) -> str:
        await asyncio.sleep(5)
        return "too late"  # pragma: no cover

    tool = register(
        Tool(
            name="TestSlow",
            description="test-only tool that never finishes in time",
            input_schema={"type": "object", "properties": {}},
            handler=_handler,
            timeout_seconds=0.05,  # explicit override beats the category map
        )
    )
    yield tool
    REGISTRY.pop("TestSlow", None)


async def test_timeout_returns_error_string(slow_tool):
    out = await execute_tool("TestSlow", {})
    assert out.startswith("Error")
    assert "TestSlow timed out" in out


def test_category_budgets_resolve_from_spec():
    """Budgets live on the tool spec: explicit timeout_seconds wins, then the
    category map, then the default."""
    def make(category: str, timeout: float | None = None) -> Tool:
        async def _h(args: dict) -> str:
            return "ok"

        return Tool(
            name="t",
            description="d",
            input_schema={},
            handler=_h,
            category=category,
            timeout_seconds=timeout,
        )

    assert make("research").effective_timeout_seconds == 60.0
    assert make("gmail").effective_timeout_seconds == 60.0
    assert make("calendar").effective_timeout_seconds == 60.0
    assert make("documents").effective_timeout_seconds == 30.0
    # Local-only categories fall through to the 15s default.
    assert make("memory").effective_timeout_seconds == DEFAULT_TOOL_TIMEOUT_SECONDS
    assert make("pm").effective_timeout_seconds == DEFAULT_TOOL_TIMEOUT_SECONDS
    assert make("utility").effective_timeout_seconds == DEFAULT_TOOL_TIMEOUT_SECONDS
    # Explicit override beats everything.
    assert make("research", timeout=5.0).effective_timeout_seconds == 5.0
