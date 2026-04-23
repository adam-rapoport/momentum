"""Smoke test: full tool-calling loop against Groq without the DB or WebSocket.

Simulates one conversational turn: user asks a question, model chooses to
call a tool, we execute it, we feed the result back, model produces a final
answer. Lets us verify Groq's tool-call streaming format works end-to-end.

Usage:
  .venv/bin/python -m scripts.try_tool_loop
  .venv/bin/python -m scripts.try_tool_loop "what is today's date?"
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.groq_client import StreamChunk, StreamResult, stream_message
from app.core.tools import _load_builtin_tools, all_tools, execute_tool, to_openai_tools

_load_builtin_tools()


async def main() -> None:
    user_text = sys.argv[1] if len(sys.argv) > 1 else "What is today's date and time?"
    tool_specs = to_openai_tools(all_tools())

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are pMomentum. When the user asks about the current date or "
                "time, call the TimeCheck tool. Never guess the date."
            ),
        },
        {"role": "user", "content": user_text},
    ]

    print(f"[try_tool_loop] model: {settings.groq_model}")
    print(f"[try_tool_loop] tools: {[t.name for t in all_tools()]}")
    print(f"[try_tool_loop] user: {user_text}\n")

    for i in range(4):
        print(f"--- iteration {i + 1} ---")
        assistant_text_chunks: list[str] = []
        result: StreamResult | None = None
        async for ev in stream_message(messages, tools=tool_specs):
            if isinstance(ev, StreamChunk):
                print(ev.text, end="", flush=True)
                assistant_text_chunks.append(ev.text)
            elif isinstance(ev, StreamResult):
                result = ev
        print()

        if result is None:
            print("[try_tool_loop] no result from stream")
            return

        assistant_text = "".join(assistant_text_chunks)
        print(
            f"[try_tool_loop] finish={result.finish_reason}  "
            f"in={result.input_tokens} out={result.output_tokens} "
            f"cost=${result.cost_usd}  tool_calls={len(result.tool_calls)}"
        )

        # Append assistant turn
        assistant_entry: dict = {"role": "assistant", "content": assistant_text or None}
        if result.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments_json},
                }
                for tc in result.tool_calls
            ]
        messages.append(assistant_entry)

        if not result.tool_calls:
            print("\n[try_tool_loop] done — no more tool calls")
            return

        for tc in result.tool_calls:
            try:
                parsed = json.loads(tc.arguments_json) if tc.arguments_json else {}
            except json.JSONDecodeError:
                parsed = {}
            print(f"[try_tool_loop] executing {tc.name}({parsed})")
            output = await execute_tool(tc.name, parsed)
            print(f"[try_tool_loop] → {output}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

    print("[try_tool_loop] hit iteration cap")


if __name__ == "__main__":
    asyncio.run(main())
