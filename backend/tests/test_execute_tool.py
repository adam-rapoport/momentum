"""execute_tool error-contract tests (plan item 31 / T-A23).

The session engine detects tool failure via `output.startswith("Error")`
(session_engine.py:782) — these tests pin that contract so a refactor of the
registry can't silently break error propagation to the model.
"""
from __future__ import annotations

import pytest

from app.core.tools import (
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
