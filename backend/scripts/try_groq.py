"""Smoke test: stream a single message from Groq to the terminal.

Usage:
  .venv/bin/python -m scripts.try_groq "your prompt here"
  .venv/bin/python -m scripts.try_groq           # uses a default prompt
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.groq_client import stream_message
from app.core.llm_types import StreamChunk, StreamResult


async def main() -> None:
    prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "In two sentences, what are the three most common failure modes of a PM writing a PRD?"
    )

    messages = [
        {
            "role": "system",
            "content": "You are pMomentum, an AI assistant for Product Managers. Be direct and concise.",
        },
        {"role": "user", "content": prompt},
    ]

    print(f"[try_groq] model: {settings.groq_model}")
    print(f"[try_groq] prompt: {prompt}\n")
    print("--- response ---")

    async for event in stream_message(messages):
        if isinstance(event, StreamChunk):
            print(event.text, end="", flush=True)
        elif isinstance(event, StreamResult):
            print("\n--- end ---")
            print(
                f"Input tokens: {event.input_tokens}  "
                f"Output tokens: {event.output_tokens}  "
                f"Cost: ${event.cost_usd}"
            )


if __name__ == "__main__":
    asyncio.run(main())
