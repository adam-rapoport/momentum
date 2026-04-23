"""Smoke test: connect to the WebSocket endpoint, send a message,
print the streamed response.

Requires the server to be running on port 8000.

Usage:
  .venv/bin/python -m scripts.try_ws <session_id> "your prompt"
"""
import asyncio
import json
import sys

import websockets


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.try_ws <session_id> [prompt]")
        sys.exit(1)

    session_id = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Say hello in one short sentence."

    url = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(url) as ws:
        await ws.send(
            json.dumps({"type": "session.message", "session_id": session_id, "content": prompt})
        )

        while True:
            raw = await ws.recv()
            event = json.loads(raw)
            t = event["type"]
            if t == "stream.text":
                print(event["text"], end="", flush=True)
            elif t == "stream.tool_start":
                print(f"\n  [tool.start] {event['name']} input={event['input']}")
            elif t == "stream.tool_result":
                tag = "ERROR" if event.get("is_error") else "ok"
                preview = event["output"][:160].replace("\n", " ")
                print(f"  [tool.result:{tag}] {event['name']} -> {preview}{'…' if len(event['output'])>160 else ''}")
            elif t == "stream.done":
                print("\n--- done ---")
                usage = event["usage"]
                print(
                    f"input={usage['input_tokens']} output={usage['output_tokens']} "
                    f"cost=${usage['cost_usd']} total=${usage['total_cost_usd']}"
                )
                if event["metadata"].get("cancelled"):
                    print("(cancelled)")
                break
            elif t == "error":
                print(f"\n[error] {event['code']}: {event['message']}")
                break


if __name__ == "__main__":
    asyncio.run(main())
