"""Routing tests for app.core.llm.stream_message.

Dispatch is registry-driven: a model's REGISTRY entry decides which client
serves it (provider + the `client` marker for Google). Models that aren't in
the registry fall back to the original name-prefix rule. These tests stub each
client's `stream_message` and assert the right one is chosen — no network.
"""
from __future__ import annotations

import pytest

from app.core import llm, model_registry
from app.core.llm_types import StreamResult


@pytest.fixture
def record_clients(monkeypatch):
    """Replace every provider client's stream_message with a stub that records
    which client was invoked, then yields one trivial StreamResult."""
    calls: list[tuple[str, str, str | None]] = []

    def make(label: str):
        async def fake_stream_message(messages, model, tools=None, api_key=None):
            calls.append((label, model, api_key))
            yield StreamResult(text="ok")

        return fake_stream_message

    monkeypatch.setattr(llm.google_client, "stream_message", make("google_compat"))
    monkeypatch.setattr(llm.google_genai_client, "stream_message", make("google_genai"))
    monkeypatch.setattr(llm.openai_client, "stream_message", make("openai"))
    monkeypatch.setattr(llm.groq_client, "stream_message", make("groq"))
    return calls


async def _drain(model: str, api_key: str | None = None) -> None:
    async for _ in llm.stream_message(
        [{"role": "user", "content": "hi"}], model=model, api_key=api_key
    ):
        pass


def _first_id(predicate) -> str | None:
    return next((m.id for m in model_registry.REGISTRY if predicate(m)), None)


async def test_routes_genai_sdk_google_models_to_native_client(record_clients):
    model = _first_id(lambda m: m.provider == "google" and m.client == "genai_sdk")
    assert model, "expected at least one genai_sdk Google entry in the registry"
    await _drain(model)
    assert record_clients[0][0] == "google_genai"


async def test_routes_compat_google_models_to_compat_client(record_clients):
    model = _first_id(lambda m: m.provider == "google" and m.client != "genai_sdk")
    assert model, "expected at least one OpenAI-compat Google entry"
    await _drain(model)
    assert record_clients[0][0] == "google_compat"


async def test_routes_openai_models_to_openai_client(record_clients):
    model = _first_id(lambda m: m.provider == "openai")
    assert model, "expected at least one OpenAI entry"
    await _drain(model)
    assert record_clients[0][0] == "openai"


async def test_routes_groq_models_to_groq_client(record_clients):
    model = _first_id(lambda m: m.provider == "groq")
    assert model, "expected at least one Groq entry"
    await _drain(model)
    assert record_clients[0][0] == "groq"


async def test_unknown_gemini_model_falls_back_to_compat(record_clients):
    # Not in the registry, but matches the gemini- prefix → compat fallback.
    model = "gemini-99-imaginary"
    assert model_registry.get_model(model) is None
    await _drain(model)
    assert record_clients[0][0] == "google_compat"


async def test_unknown_gpt_model_falls_back_to_openai(record_clients):
    # Phase 3 item 18: the prefix heuristics now live in the registry and
    # cover OpenAI ids too — an unregistered gpt-* env override must go to
    # OpenAI (whose key credentials.py resolves for it), not Groq.
    model = "gpt-99-imaginary"
    assert model_registry.get_model(model) is None
    await _drain(model)
    assert record_clients[0][0] == "openai"


async def test_unknown_other_model_falls_back_to_groq(record_clients):
    model = "some-unregistered-model-xyz"
    assert model_registry.get_model(model) is None
    await _drain(model)
    assert record_clients[0][0] == "groq"


async def test_api_key_is_threaded_through(record_clients):
    model = _first_id(lambda m: m.provider == "groq")
    await _drain(model, api_key="user-key-123")
    assert record_clients[0][2] == "user-key-123"
