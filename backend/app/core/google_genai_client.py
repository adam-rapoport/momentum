"""Native google-genai SDK client for Gemini/Gemma (F5).

This is the *second* path to Google's models, alongside the OpenAI-compatible
shim in `app.core.google_client`. The compat shim can't carry the
`thought_signature` that Gemini 3.x requires on tool-call history, which
breaks multi-step skill flows. The native SDK can, so this path unlocks the
newer models. The compat path is left untouched for Gemma / Gemini 2.5.

Contract: `stream_message` yields the same StreamChunk / StreamResult /
ToolCall objects as `groq_client`, so `app.core.llm` dispatches to either
path transparently.

Thought signatures, kept in-loop: when Gemini returns a function call, the
native SDK attaches an opaque `thought_signature` that must be replayed on
that call when we send the tool result back. Our conversation history is
stored in OpenAI format (which has no field for it), so we keep a small,
process-local cache keyed by tool-call id and re-attach the signature when we
rebuild the request. This covers the common case (several tool round-trips
inside one user turn). Cross-user-turn persistence (storing the signature in
the DB) is deliberately deferred until a multi-message flow proves it needed.

NOTE: this module is written against the documented google-genai API but
could not be exercised in the build sandbox (no network to install the real
SDK). The import is guarded so its absence never breaks app startup; calling
`stream_message` without the real SDK raises a clear error.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator

from app.config import settings
from app.core.cost_tracker import calculate_cost_usd
from app.core.llm_types import StreamChunk, StreamResult, ToolCall

logger = logging.getLogger(__name__)

try:  # The real SDK is `google-genai`; a placeholder may shadow it offline.
    from google import genai
    from google.genai import types

    _GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the SDK
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    _GENAI_AVAILABLE = False


# Process-local cache of tool-call id -> thought_signature (bytes). Bounded so
# a long-lived process can't grow it without limit; the in-loop window we care
# about is tiny (a handful of calls per turn).
_SIGNATURE_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_SIGNATURE_CACHE_MAX = 256


def _remember_signature(call_id: str, signature: bytes) -> None:
    if not call_id or not signature:
        return
    _SIGNATURE_CACHE[call_id] = signature
    _SIGNATURE_CACHE.move_to_end(call_id)
    while len(_SIGNATURE_CACHE) > _SIGNATURE_CACHE_MAX:
        _SIGNATURE_CACHE.popitem(last=False)


_clients: dict[str, "genai.Client"] = {}


def get_client(api_key: str | None = None) -> "genai.Client":
    if not _GENAI_AVAILABLE:
        raise RuntimeError(
            "The google-genai SDK is not installed. Run "
            "`pip install google-genai` to use Gemini 3.x (native SDK) models."
        )
    key = api_key or settings.google_ai_api_key
    if not key:
        raise RuntimeError(
            "GOOGLE_AI_API_KEY is not configured — set it in .env or connect "
            "Google AI Studio in Settings to route turns to Google models."
        )
    client = _clients.get(key)
    if client is None:
        client = genai.Client(api_key=key)
        _clients[key] = client
    return client


def _tools_to_genai(tools: list[dict] | None):
    """Convert OpenAI-style tool specs into a single genai Tool with one
    function declaration per tool."""
    if not tools:
        return None
    declarations = []
    for t in tools:
        fn = t.get("function", t)
        declarations.append(
            types.FunctionDeclaration(
                name=fn.get("name", ""),
                description=fn.get("description", ""),
                parameters=fn.get("parameters") or {"type": "object", "properties": {}},
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _messages_to_genai(messages: list[dict]) -> tuple[str | None, list]:
    """Translate OpenAI-format chat messages into (system_instruction, contents).

    - system           -> collected into system_instruction
    - user             -> Content(role="user", text)
    - assistant text   -> Content(role="model", text)
    - assistant tool   -> Content(role="model", function_call parts), with the
                          cached thought_signature re-attached by call id
    - tool result      -> Content(role="user", function_response part)
    """
    system_parts: list[str] = []
    contents: list = []
    # Map tool_call_id -> function name so a later tool result can name its
    # function (genai function responses are keyed by name, not id).
    call_names: dict[str, str] = {}

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            content = msg.get("content")
            if content:
                system_parts.append(content)

        elif role == "user":
            content = msg.get("content") or ""
            contents.append(
                types.Content(role="user", parts=[types.Part(text=content)])
            )

        elif role == "assistant":
            parts = []
            text = msg.get("content")
            if text:
                parts.append(types.Part(text=text))
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                call_id = tc.get("id", "")
                call_names[call_id] = name
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                part = types.Part(
                    function_call=types.FunctionCall(name=name, args=args)
                )
                signature = _SIGNATURE_CACHE.get(call_id)
                if signature:
                    part.thought_signature = signature
                parts.append(part)
            if parts:
                contents.append(types.Content(role="model", parts=parts))

        elif role == "tool":
            call_id = msg.get("tool_call_id", "")
            name = call_names.get(call_id, "")
            output = msg.get("content") or ""
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=name, response={"result": output}
                            )
                        )
                    ],
                )
            )

    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Google's native SDK. Same contract as
    `groq_client.stream_message`."""
    client = get_client(api_key)
    system_instruction, contents = _messages_to_genai(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=_tools_to_genai(tools),
    )

    collected_text: list[str] = []
    # Accumulate function calls in order, capturing their thought_signature.
    pending_calls: list[dict] = []
    input_tokens = 0
    output_tokens = 0
    finish_reason: str | None = None

    stream = await client.aio.models.generate_content_stream(
        model=model, contents=contents, config=config
    )
    async for chunk in stream:
        candidates = getattr(chunk, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in (getattr(content, "parts", None) or []):
                # Skip the model's internal reasoning ("thought") parts — they
                # shouldn't reach the UI. (Replaces the <thought> regex hack
                # the compat path needs for Gemma.)
                if getattr(part, "thought", False):
                    continue
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    pending_calls.append(
                        {
                            "name": fc.name or "",
                            "args": dict(fc.args or {}),
                            "signature": getattr(part, "thought_signature", None),
                        }
                    )
                    continue
                text = getattr(part, "text", None)
                if text:
                    collected_text.append(text)
                    yield StreamChunk(text=text)
            fr = getattr(candidate, "finish_reason", None)
            if fr is not None:
                # `fr` is a FinishReason enum (e.g. FinishReason.STOP); take its
                # bare name so it lines up with the plain "stop"/"max_tokens"
                # strings the other clients (and the warning check) expect.
                finish_reason = (getattr(fr, "name", None) or str(fr)).lower()
        usage = getattr(chunk, "usage_metadata", None)
        if usage is not None:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    tool_calls: list[ToolCall] = []
    for call in pending_calls:
        if not call["name"]:
            continue
        call_id = f"call_{uuid.uuid4().hex[:24]}"
        if call["signature"]:
            _remember_signature(call_id, call["signature"])
        tool_calls.append(
            ToolCall(
                id=call_id,
                name=call["name"],
                arguments_json=json.dumps(call["args"]),
            )
        )

    # `finish_reason` is already normalized to a bare lowercase name above.
    # Warn only on abnormal terminations (safety, recitation, truncation, …).
    if finish_reason and finish_reason not in ("stop", "tool_calls", "max_tokens"):
        logger.warning(
            "google-genai stream ended with finish_reason=%s (model=%s)",
            finish_reason, model,
        )

    yield StreamResult(
        text="".join(collected_text),
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost_usd(model, input_tokens, output_tokens),
        finish_reason=finish_reason,
    )
