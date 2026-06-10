"""Native google-genai SDK client for Gemini/Gemma (F5).

This is the *second* path to Google's models, alongside the OpenAI-compatible
shim in `app.core.google_client`. The compat shim can't carry the
`thought_signature` that Gemini 3.x requires on tool-call history, which
breaks multi-step skill flows. The native SDK can, so this path unlocks the
newer models. The compat path is left untouched for Gemma / Gemini 2.5.

Contract: `stream_message` yields the same StreamChunk / StreamResult /
ToolCall objects as the other clients, so `app.core.llm` dispatches to either
path transparently.

Thought signatures (Phase 3 item 19, findings A12/A13): when Gemini returns a
function call, the SDK attaches an opaque `thought_signature` (bytes) that
must be replayed on that call whenever it reappears in request history. We
surface it base64-encoded on `ToolCall.thought_signature`; the session engine
persists it inside the tool_use content block (so it survives restarts and
round-trips through Message.content) and threads it back through the
assistant message's tool_calls, where `_messages_to_genai` re-attaches it.
This replaces an earlier process-local cache that was lost on every sidecar
restart.

Translation details verified against the vendored google-genai SDK (v2.8.0):
  - Tool parameters are passed as `parameters_json_schema`, which accepts raw
    JSON Schema natively (the SDK itself recommends it over converting to
    `types.Schema`, whose `extra='forbid'` model would reject any JSON-Schema
    key it doesn't model).
  - Parallel function calls arrive as multiple parts in ONE model Content, so
    their results must go back as multiple function_response parts in ONE
    user Content — consecutive tool messages are grouped accordingly.
  - `Part.thought_signature` is a declared `Optional[bytes]` field, set at
    construction time.
"""
from __future__ import annotations

import base64
import json
import logging
import uuid
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
    function declaration per tool. Parameters go through
    `parameters_json_schema` — the SDK field that takes raw JSON Schema —
    so our OpenAI-format schemas (additionalProperties and all) pass
    through unconverted."""
    if not tools:
        return None
    declarations = []
    for t in tools:
        fn = t.get("function", t)
        declarations.append(
            types.FunctionDeclaration(
                name=fn.get("name", ""),
                description=fn.get("description", ""),
                parameters_json_schema=fn.get("parameters")
                or {"type": "object", "properties": {}},
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _decode_signature(value) -> bytes | None:
    """Base64 string (as stored in Message.content) -> raw bytes for the SDK.
    Tolerates garbage — a corrupt signature must not kill the turn."""
    if not value or not isinstance(value, str):
        return None
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        logger.warning("dropping undecodable thought_signature")
        return None


def _messages_to_genai(messages: list[dict]) -> tuple[str | None, list]:
    """Translate OpenAI-format chat messages into (system_instruction, contents).

    - system           -> collected into system_instruction
    - user             -> Content(role="user", text)
    - assistant text   -> Content(role="model", text)
    - assistant tool   -> Content(role="model", function_call parts), with the
                          persisted thought_signature re-attached per call
    - tool result      -> function_response part; CONSECUTIVE tool results are
                          grouped into one Content(role="user") to mirror how
                          the parallel calls arrived in one model Content
    """
    system_parts: list[str] = []
    contents: list = []
    # Map tool_call_id -> function name so a later tool result can name its
    # function (genai function responses are keyed by name, not id).
    call_names: dict[str, str] = {}
    # Function-response parts being accumulated; flushed into one Content when
    # a non-tool message (or the end of the input) is reached.
    pending_responses: list = []

    def _flush_responses() -> None:
        if pending_responses:
            contents.append(
                types.Content(role="user", parts=list(pending_responses))
            )
            pending_responses.clear()

    for msg in messages:
        role = msg.get("role")
        if role != "tool":
            _flush_responses()

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
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(name=name, args=args),
                        thought_signature=_decode_signature(
                            tc.get("thought_signature")
                        ),
                    )
                )
            if parts:
                contents.append(types.Content(role="model", parts=parts))

        elif role == "tool":
            call_id = msg.get("tool_call_id", "")
            name = call_names.get(call_id, "")
            output = msg.get("content") or ""
            pending_responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=name, response={"result": output}
                    )
                )
            )

    _flush_responses()
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
        signature = call["signature"]
        tool_calls.append(
            ToolCall(
                id=call_id,
                name=call["name"],
                arguments_json=json.dumps(call["args"]),
                # Base64 so it can live inside a JSON content block; the
                # session engine persists it with the tool_use block and
                # _messages_to_genai decodes it on replay.
                thought_signature=(
                    base64.b64encode(signature).decode("ascii")
                    if signature
                    else None
                ),
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
