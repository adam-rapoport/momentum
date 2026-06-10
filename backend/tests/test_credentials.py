"""Unit tests for the pure-logic parts of app.core.credentials (C8).

DB round-trip behavior (store/resolve/delete) is covered by the
scripts/try_credentials.py smoke test against a real Postgres + vault key.
"""
from __future__ import annotations

import pytest

from app.core import credentials


def test_llm_provider_for_model_maps_google_prefixes():
    assert credentials.llm_provider_for_model("gemini-2.5-flash") == "llm:google_ai"
    assert credentials.llm_provider_for_model("gemma-4-31b-it") == "llm:google_ai"


def test_llm_provider_for_model_maps_openai_prefixes():
    assert credentials.llm_provider_for_model("gpt-4o") == "llm:openai"
    assert credentials.llm_provider_for_model("gpt-4o-mini") == "llm:openai"
    assert credentials.llm_provider_for_model("o3-mini") == "llm:openai"


def test_llm_provider_for_model_defaults_to_groq():
    assert (
        credentials.llm_provider_for_model("meta-llama/llama-4-scout-17b-16e-instruct")
        == "llm:groq"
    )
    assert credentials.llm_provider_for_model("llama-3.1-8b-instant") == "llm:groq"


def test_llm_provider_for_model_consults_registry_first(monkeypatch):
    # Phase 3 item 18 (finding A17): a registry entry beats the prefix
    # heuristic. An id that LOOKS like OpenAI but is registered on Groq must
    # resolve to the Groq key.
    from app.core import model_registry

    entry = model_registry.ModelEntry(
        id="gpt-hosted-on-groq", provider="groq", display_name="x", role="light"
    )
    monkeypatch.setattr(
        model_registry, "REGISTRY", (*model_registry.REGISTRY, entry)
    )
    assert credentials.llm_provider_for_model("gpt-hosted-on-groq") == "llm:groq"
    # Registry entries with no heuristically-matching prefix work too.
    assert credentials.llm_provider_for_model("openai/gpt-oss-120b") == "llm:groq"


def test_known_providers_namespaced_and_disjoint():
    assert set(credentials.LLM_PROVIDERS) == {"llm:groq", "llm:google_ai", "llm:openai"}
    assert set(credentials.SEARCH_PROVIDERS) == {"search:tavily", "search:perplexity"}
    # no overlap, and KEY_PROVIDERS is the union
    assert not (set(credentials.LLM_PROVIDERS) & set(credentials.SEARCH_PROVIDERS))
    assert set(credentials.KEY_PROVIDERS) == set(credentials.LLM_PROVIDERS) | set(
        credentials.SEARCH_PROVIDERS
    )


def test_env_fallback_reads_settings(monkeypatch):
    monkeypatch.setattr(credentials.settings, "groq_api_key", "gsk_env_value")
    monkeypatch.setattr(credentials.settings, "perplexity_api_key", None)
    assert credentials._env_fallback("llm:groq") == "gsk_env_value"
    assert credentials._env_fallback("search:perplexity") is None
    assert credentials._env_fallback("not-a-provider") is None
