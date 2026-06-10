"""End-to-end smoke test for the F5 native google-genai client.

Unlike try_google (which uses the OpenAI-compat endpoint), this exercises the
native SDK path in app.core.google_genai_client — including the tool-call
round-trip that replays Gemini's thought_signature, the thing the compat path
can't do. Defaults to a Gemini 3 model (SDK-only).

Usage:
  .venv/bin/python -m scripts.try_google_sdk
  .venv/bin/python -m scripts.try_google_sdk gemini-3.1-pro-preview  # override
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.google_genai_client import _SIGNATURE_CACHE, stream_message
from app.core.llm_types import StreamChunk, StreamResult

DEFAULT_MODEL = "gemini-3-flash-preview"

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}


async def _collect(messages, model, tools):
    """Drain a stream, printing text deltas; return the final StreamResult."""
    result: StreamResult | None = None
    async for event in stream_message(messages, model=model, tools=tools):
        if isinstance(event, StreamChunk):
            print(event.text, end="", flush=True)
        elif isinstance(event, StreamResult):
            result = event
    print()
    return result


async def main() -> None:
    if not settings.google_ai_api_key:
        print("GOOGLE_AI_API_KEY is not set in .env")
        sys.exit(1)

    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"Using model (native SDK): {model}\n")

    system = (
        "You are a helpful assistant. When asked about the weather, call the "
        "get_weather tool. After receiving the result, answer in one sentence."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "What's the weather in Paris? Use the tool."},
    ]

    try:
        print("--- turn 1: expect a tool call ---")
        r1 = await _collect(messages, model, [WEATHER_TOOL])
        if r1 is None:
            print("FAILED: stream ended without a StreamResult")
            sys.exit(1)
        print(f"tool_calls: {len(r1.tool_calls)}  signatures cached: {len(_SIGNATURE_CACHE)}")
        for tc in r1.tool_calls:
            print(f"  - {tc.name}({tc.arguments_json})  id={tc.id}")

        if not r1.tool_calls:
            print("\nModel declined to call the tool; can't test the round-trip.")
            print(f"tokens in/out: {r1.input_tokens}/{r1.output_tokens}  cost: ${r1.cost_usd}")
            return

        tc = r1.tool_calls[0]
        messages += [
            {
                "role": "assistant",
                "content": r1.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments_json},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": '{"temp_c": 14, "sky": "cloudy"}',
            },
        ]

        print("\n--- turn 2: feed tool result back (replays thought_signature) ---")
        r2 = await _collect(messages, model, [WEATHER_TOOL])
        if r2 is None:
            print("FAILED: round-trip ended without a StreamResult")
            sys.exit(1)
        print("=" * 60)
        print(f"finish_reason:  {r2.finish_reason}")
        print(f"tokens in/out:  {r2.input_tokens}/{r2.output_tokens}")
        print(f"cost_usd:       ${r2.cost_usd}")
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        sys.exit(1)

    print("\nSmoke test complete.")


if __name__ == "__main__":
    asyncio.run(main())
