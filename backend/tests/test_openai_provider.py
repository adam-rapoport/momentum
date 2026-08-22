"""Unit tests for the additive OpenAI provider (registry + client basics).

The dispatch path is covered in test_llm_dispatch; credential mapping in
test_credentials. Live streaming is covered by scripts/try_openai.py.
"""
from __future__ import annotations

import pytest

from app.core import model_registry, openai_client


def test_openai_models_registered():
    openai_ids = {m.id for m in model_registry.REGISTRY if m.provider == "openai"}
    assert "gpt-5.4" in openai_ids
    assert "gpt-5.6-luna" in openai_ids
    # The original gpt-5 family was retired Aug 2026 (OpenAI shutdown Dec 2026).
    assert "gpt-5" not in openai_ids


def test_openai_models_visible_only_when_provider_configured():
    visible = {
        m.id
        for m in model_registry.get_available_models(
            configured_providers={"openai"}
        )
    }
    assert "gpt-5.4" in visible
    # Other providers' models are hidden when only OpenAI is configured.
    assert all(
        m.id not in visible
        for m in model_registry.REGISTRY
        if m.provider != "openai"
    )


def test_openai_models_hidden_when_provider_absent():
    visible = {
        m.id
        for m in model_registry.get_available_models(
            configured_providers={"groq", "google"}
        )
    }
    assert all(
        m.id not in visible
        for m in model_registry.REGISTRY
        if m.provider == "openai"
    )


def test_get_client_raises_clearly_without_key(monkeypatch):
    monkeypatch.setattr(openai_client.settings, "openai_api_key", None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        openai_client.get_client(api_key=None)


def test_get_client_caches_by_key():
    openai_client._clients.clear()
    c1 = openai_client.get_client(api_key="sk-test-key")
    c2 = openai_client.get_client(api_key="sk-test-key")
    assert c1 is c2
    openai_client._clients.clear()
