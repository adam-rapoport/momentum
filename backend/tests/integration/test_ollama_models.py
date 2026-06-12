"""GET /api/v1/connections/ollama/models — the dynamic local-model list.

All Ollama HTTP traffic is mocked (httpx.MockTransport); no live server.
"""
from __future__ import annotations

import httpx
import pytest

from app.api import connections as connections_mod
from app.core import credentials

API = "/api/v1"


def _const_async(value):
    async def _f(*args, **kwargs):
        return value

    return _f


def _mock_ollama(monkeypatch, handler):
    real = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def _factory(**kwargs):
        kwargs.pop("transport", None)
        return real(transport=transport, **kwargs)

    monkeypatch.setattr(connections_mod.httpx, "AsyncClient", _factory)


def test_ollama_models_requires_connection(client, monkeypatch):
    monkeypatch.setattr(credentials, "resolve_api_key", _const_async(None))
    res = client.get(f"{API}/connections/ollama/models")
    assert res.status_code == 400


def test_ollama_models_lists_and_probes_capabilities(client, monkeypatch):
    monkeypatch.setattr(
        credentials, "resolve_api_key", _const_async("http://localhost:11434/")
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "llama3.1:8b"},
                        {"name": "tinyllama:latest"},
                    ]
                },
            )
        if request.url.path == "/api/show":
            body = request.read().decode()
            if "llama3.1:8b" in body:
                return httpx.Response(
                    200,
                    json={
                        "capabilities": ["completion", "tools"],
                        "model_info": {"llama.context_length": 131072},
                    },
                )
            # The probe is best-effort: a failing /api/show must not drop
            # the model from the list.
            return httpx.Response(500)
        return httpx.Response(404)

    _mock_ollama(monkeypatch, handler)

    res = client.get(f"{API}/connections/ollama/models")
    assert res.status_code == 200
    body = res.json()
    assert body["base_url"] == "http://localhost:11434"
    by_id = {m["id"]: m for m in body["models"]}
    assert set(by_id) == {"ollama:llama3.1:8b", "ollama:tinyllama:latest"}
    assert by_id["ollama:llama3.1:8b"]["supports_tools"] is True
    assert by_id["ollama:llama3.1:8b"]["context_length"] == 131072
    assert by_id["ollama:tinyllama:latest"]["supports_tools"] is False
    assert by_id["ollama:tinyllama:latest"]["context_length"] is None


def test_ollama_models_unreachable_server_is_502(client, monkeypatch):
    monkeypatch.setattr(
        credentials, "resolve_api_key", _const_async("http://localhost:11434")
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _mock_ollama(monkeypatch, handler)
    res = client.get(f"{API}/connections/ollama/models")
    assert res.status_code == 502


@pytest.mark.asyncio
async def test_validate_ollama_rejects_non_url():
    from app.core.key_validation import _validate_ollama

    result = await _validate_ollama("not a url")
    assert not result.ok
