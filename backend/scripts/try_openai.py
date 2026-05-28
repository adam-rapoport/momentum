"""End-to-end smoke test for the OpenAI client (additive paid provider).

Hits OpenAI directly with a minimal prompt + one fake tool and prints every
stream event. Needs OPENAI_API_KEY (a billing-enabled key) in .env.

Usage:
  .venv/bin/python -m scripts.try_openai
  .venv/bin/python -m scripts.try_openai gpt-4o   # override model
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.groq_client import StreamChunk, StreamResult
from app.core.openai_client import stream_message

DEFAULT_MODEL = "gpt-4o-mini"

FAKE_WRITE_DOC_TOOL = {
    "type": "function",
    "function": {
        "name": "WriteDocument",
        "description": "Write a markdown document to the user's workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content_markdown": {"type": "string"},
            },
            "required": ["title", "content_markdown"],
        },
    },
}


async def main() -> None:
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"Using model: {model}\n")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful PM assistant. Respond concisely. When the "
                "user asks you to create a document, call the WriteDocument "
                "tool with a title and a short markdown body."
            ),
        },
        {
            "role": "user",
            "content": "Write a tiny PRD draft for a dark-mode toggle. Two short sections.",
        },
    ]

    text_chunks: list[str] = []
    got_result = False
    try:
        async for event in stream_message(
            messages, model=model, tools=[FAKE_WRITE_DOC_TOOL]
        ):
            if isinstance(event, StreamChunk):
                text_chunks.append(event.text)
                print(event.text, end="", flush=True)
            elif isinstance(event, StreamResult):
                got_result = True
                print()
                print()
                print("=" * 60)
                print(f"input_tokens:   {event.input_tokens}")
                print(f"output_tokens:  {event.output_tokens}")
                print(f"cost_usd:       ${event.cost_usd}")
                print(f"finish_reason:  {event.finish_reason}")
                print(f"tool_calls:     {len(event.tool_calls)}")
                for tc in event.tool_calls:
                    print(f"  - {tc.name}({tc.arguments_json[:120]}...)")
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        sys.exit(1)

    if not got_result:
        print("\nFAILED: stream ended without a StreamResult")
        sys.exit(1)

    print()
    print("Smoke test complete.")


if __name__ == "__main__":
    asyncio.run(main())
