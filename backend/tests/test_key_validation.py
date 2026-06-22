"""Unit tests for app.core.key_validation routing + the httpx-based
Anthropic validator. All transports are mocked — no network."""
from __future__ import annotations

import httpx
import pytest

from app.core import key_validation as kv


def _mock_async_client(monkeypatch, status_code: int):
    """Make kv's `httpx.AsyncClient(...)` return a client whose every request
    answers with `status_code`."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, json={})
    )
    real = httpx.AsyncClient

    def _factory(**kwargs):
        kwargs.pop("transport", None)
        return real(transport=transport, **kwargs)

    monkeypatch.setattr(kv.httpx, "AsyncClient", _factory)


async def test_validate_anthropic_ok(monkeypatch):
    _mock_async_client(monkeypatch, 200)
    result = await kv._validate_anthropic("sk-ant-test")
    assert result.ok


async def test_validate_anthropic_rejected(monkeypatch):
    _mock_async_client(monkeypatch, 401)
    result = await kv._validate_anthropic("sk-ant-bad")
    assert not result.ok


async def test_validate_anthropic_rate_limited_is_valid(monkeypatch):
    _mock_async_client(monkeypatch, 429)
    result = await kv._validate_anthropic("sk-ant-test")
    assert result.ok
    assert "rate-limited" in result.detail


async def test_validate_key_routes_anthropic(monkeypatch):
    seen = {}

    async def _fake(key):
        seen["key"] = key
        return kv.ValidationResult(True, "ok")

    monkeypatch.setattr(kv, "_validate_anthropic", _fake)
    result = await kv.validate_key("llm:anthropic", "sk-ant-x")
    assert result.ok and seen["key"] == "sk-ant-x"


async def test_validate_key_routes_mistral_to_models_list(monkeypatch):
    seen = {}

    async def _fake(key, base_url):
        seen.update(key=key, base_url=base_url)
        return kv.ValidationResult(True, "ok")

    monkeypatch.setattr(kv, "_validate_models_list", _fake)
    result = await kv.validate_key("llm:mistral", "mk-x")
    assert result.ok
    assert seen["base_url"] == kv.MISTRAL_BASE_URL


async def test_validate_key_routes_openrouter_to_key_endpoint(monkeypatch):
    seen = {}

    async def _fake(key):
        seen["key"] = key
        return kv.ValidationResult(True, "ok")

    monkeypatch.setattr(kv, "_validate_openrouter", _fake)
    result = await kv.validate_key("llm:openrouter", "sk-or-x")
    assert result.ok and seen["key"] == "sk-or-x"


async def test_validate_key_routes_openai_to_models_list(monkeypatch):
    seen = {}

    async def _fake(key, base_url):
        seen.update(key=key, base_url=base_url)
        return kv.ValidationResult(True, "ok")

    monkeypatch.setattr(kv, "_validate_models_list", _fake)
    result = await kv.validate_key("llm:openai", "sk-x")
    assert result.ok
    assert seen["base_url"] == kv.OPENAI_BASE_URL


async def test_validate_openrouter_ok(monkeypatch):
    _mock_async_client(monkeypatch, 200)
    result = await kv._validate_openrouter("sk-or-test")
    assert result.ok


async def test_validate_openrouter_rejected(monkeypatch):
    _mock_async_client(monkeypatch, 401)
    result = await kv._validate_openrouter("sk-or-bad")
    assert not result.ok


async def test_validate_key_rejects_empty_key():
    result = await kv.validate_key("llm:anthropic", "   ")
    assert not result.ok


async def test_validate_key_unknown_provider_raises():
    with pytest.raises(ValueError):
        await kv.validate_key("llm:imaginary", "key")
