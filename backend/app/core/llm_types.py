"""Provider-neutral streaming types shared by every LLM client.

Moved out of `groq_client` (finding A31) so no single provider module owns
the wire contract. `groq_client` re-exports these names for backward
compatibility — the test harness and older callers import from there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class StreamChunk:
    text: str


@dataclass
class ToolCall:
    """A tool call requested by the LLM. `arguments_json` is a raw JSON string
    as emitted by the model — we leave parsing to the caller so we don't
    choke a whole stream on one bad call.

    `thought_signature` (base64 string) is Gemini-specific: the native
    google-genai SDK attaches an opaque signature to each function call that
    MUST be replayed when the call appears in later request history. The
    session engine persists it inside the tool_use content block so it
    round-trips through Message.content; non-Google providers ignore it.
    """
    id: str
    name: str
    arguments_json: str
    thought_signature: str | None = None


@dataclass
class StreamResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    finish_reason: str | None = None
