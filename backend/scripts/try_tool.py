"""Smoke test: call a registered tool directly, bypassing the LLM.

Usage:
  .venv/bin/python -m scripts.try_tool TimeCheck
  .venv/bin/python -m scripts.try_tool TimeCheck '{}'
  .venv/bin/python -m scripts.try_tool <ToolName> '{"arg": "value"}'
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.tools import _load_builtin_tools, all_tools, execute_tool

_load_builtin_tools()


async def main() -> None:
    if len(sys.argv) < 2:
        print("Registered tools:")
        for t in all_tools():
            print(f"  {t.name}  —  {t.description[:80]}")
        return

    name = sys.argv[1]
    raw_args = sys.argv[2] if len(sys.argv) > 2 else "{}"
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError as e:
        print(f"[try_tool] invalid JSON input: {e}")
        sys.exit(1)

    print(f"[try_tool] calling {name} with input: {args}")
    output = await execute_tool(name, args)
    print("--- output ---")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
