"""REST API contract tests — plan item 30 (T5).

Sessions CRUD in full (the frontend's primary REST surface), plus smoke
coverage of the preferences and connections endpoints and the Phase 0 local
trust boundary (Host / Origin / X-PMomentum-Token middleware).

Runs the real app via the `client` fixture; the lifespan seeds the default
single-user workspace, so `get_default_user` resolves without extra setup.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.core.integrations import vault

API = "/api/v1"


@pytest.fixture
def vault_key(monkeypatch):
    """Configure a throwaway Fernet vault key. `vault._fernet` is lru_cached,
    so the cache must be cleared both when installing and when removing it."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "credential_vault_key", key)
    vault._fernet.cache_clear()
    yield key
    vault._fernet.cache_clear()


# ---------- sessions CRUD ----------


def test_create_session_defaults(client):
    resp = client.post(f"{API}/sessions", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] is None
    assert body["status"] == "active"
    assert body["turn_count"] == 0
    assert float(body["total_cost_usd"]) == 0.0  # Decimal serialized as a string
    assert body["session_metadata"] == {}
    # Bound to the seeded default workspace.
    assert body["user_id"] and body["project_id"]


def test_create_session_with_title_then_list(client):
    created = client.post(f"{API}/sessions", json={"title": "My session"}).json()
    listed = client.get(f"{API}/sessions").json()
    assert [s["id"] for s in listed] == [created["id"]]
    assert listed[0]["title"] == "My session"


def test_get_session_detail_includes_messages_and_metadata(client):
    created = client.post(f"{API}/sessions", json={"title": "detail"}).json()
    resp = client.get(f"{API}/sessions/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["messages"] == []
    assert body["session_metadata"] == {}
    # The raw DB column name must not leak alongside the renamed field.
    assert "metadata" not in body


def test_patch_session_title_and_status(client):
    created = client.post(f"{API}/sessions", json={}).json()
    resp = client.patch(
        f"{API}/sessions/{created['id']}",
        json={"title": "renamed", "status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "renamed"
    assert resp.json()["status"] == "completed"


def test_patch_rejects_invalid_status(client):
    created = client.post(f"{API}/sessions", json={}).json()
    resp = client.patch(f"{API}/sessions/{created['id']}", json={"status": "exploded"})
    assert resp.status_code == 422


def test_delete_archives_and_hides_from_list(client):
    created = client.post(f"{API}/sessions", json={}).json()
    resp = client.delete(f"{API}/sessions/{created['id']}")
    assert resp.status_code == 204

    # Archived sessions disappear from the list but stay fetchable by id.
    assert client.get(f"{API}/sessions").json() == []
    detail = client.get(f"{API}/sessions/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "archived"


def test_session_endpoints_404_on_unknown_id(client):
    missing = uuid4()
    assert client.get(f"{API}/sessions/{missing}").status_code == 404
    assert client.patch(f"{API}/sessions/{missing}", json={"title": "x"}).status_code == 404
    assert client.delete(f"{API}/sessions/{missing}").status_code == 404


# ---------- Phase 0 trust boundary (HTTP middleware) ----------


def test_forbidden_host_rejected(client):
    resp = client.get(f"{API}/sessions", headers={"host": "evil.example"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "forbidden host"}


def test_forbidden_origin_rejected(client):
    resp = client.get(f"{API}/sessions", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "forbidden origin"}


def test_allowed_origin_passes(client):
    resp = client.get(f"{API}/sessions", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200


def test_token_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "per-launch-secret")

    assert client.get(f"{API}/sessions").status_code == 401
    assert (
        client.get(f"{API}/sessions", headers={"X-PMomentum-Token": "wrong"}).status_code
        == 401
    )
    assert (
        client.get(
            f"{API}/sessions", headers={"X-PMomentum-Token": "per-launch-secret"}
        ).status_code
        == 200
    )
    # /health is the boot-gate poll — token-exempt by design.
    assert client.get("/health").status_code == 200


def test_cors_preflight_bypasses_token(client, monkeypatch):
    """The packaged-app regression (2026-06): the token header makes every
    webview request non-simple, so the browser preflights with OPTIONS — which
    by design carries NO custom headers. CORSMiddleware must answer the
    preflight before the trust boundary's token check, or the desktop app
    401s every preflight and the UI can never reach the backend (it sticks on
    the boot screen forever). Asserts the exact request shape the Tauri
    webview sends."""
    monkeypatch.setattr(settings, "auth_token", "per-launch-secret")

    resp = client.options(
        f"{API}/onboarding/status",
        headers={
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type,x-pmomentum-token",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "tauri://localhost"
    assert "x-pmomentum-token" in resp.headers["access-control-allow-headers"].lower()

    # The real (post-preflight) request still requires the token: the
    # preflight exemption must not weaken the trust boundary itself.
    assert (
        client.get(
            f"{API}/onboarding/status", headers={"Origin": "tauri://localhost"}
        ).status_code
        == 401
    )


# ---------- preferences (smoke) ----------


def test_get_model_preferences_shape(client):
    body = client.get(f"{API}/preferences/models").json()
    assert body["light_model"] is None
    assert body["heavy_model"] is None
    assert body["effective_light_model"] == settings.groq_model
    assert body["effective_heavy_model"] == settings.groq_heavy_model
    assert isinstance(body["available_light_models"], list)
    assert isinstance(body["available_heavy_models"], list)


def test_put_model_preferences_roundtrip(client):
    # Pick a real registry model whose provider is configured in this run.
    available = client.get(f"{API}/preferences/models").json()["available_light_models"]
    if not available:
        pytest.skip("no provider keys configured in this environment")
    pick = available[0]["id"]

    updated = client.put(f"{API}/preferences/models", json={"light_model": pick}).json()
    assert updated["light_model"] == pick
    assert updated["effective_light_model"] == pick

    # Clearing with an empty string falls back to the env default.
    cleared = client.put(f"{API}/preferences/models", json={"light_model": ""}).json()
    assert cleared["light_model"] is None
    assert cleared["effective_light_model"] == settings.groq_model


def test_put_model_preferences_rejects_unknown_model(client):
    resp = client.put(
        f"{API}/preferences/models", json={"heavy_model": "not-a-real-model"}
    )
    assert resp.status_code == 400


def test_profile_roundtrip(client):
    resp = client.put(
        f"{API}/preferences/profile",
        json={"display_name": "Avery", "workspace_name": "Avery's Workspace"},
    )
    assert resp.status_code == 200
    body = client.get(f"{API}/preferences/profile").json()
    assert body == {"display_name": "Avery", "workspace_name": "Avery's Workspace"}


def test_search_preferences_validation(client):
    assert client.put(f"{API}/preferences/search", json={"provider": "askjeeves"}).status_code == 400
    assert client.put(f"{API}/preferences/search", json={"provider": "tavily"}).json() == {
        "provider": "tavily"
    }


# ---------- connections (smoke) ----------


def test_list_connections_reports_all_key_providers(client):
    body = client.get(f"{API}/connections").json()
    providers = {c["provider"] for c in body["connections"]}
    assert providers == {
        "llm:groq",
        "llm:google_ai",
        "llm:openai",
        "search:tavily",
        "search:perplexity",
    }
    # No secrets in the status payload.
    for conn in body["connections"]:
        assert set(conn) <= {
            "provider",
            "configured",
            "source",
            "key_suffix",
            "status",
            "last_validated_at",
            "last_error",
        }


def test_unknown_connection_provider_404(client):
    assert client.put(
        f"{API}/connections/llm:nope", json={"api_key": "k"}
    ).status_code == 404
    assert client.delete(f"{API}/connections/llm:nope").status_code == 404


def test_put_connection_stores_validated_key(client, vault_key):
    ok = SimpleNamespace(ok=True, detail="Key validated.")
    with patch("app.api.connections.validate_key", new=AsyncMock(return_value=ok)):
        resp = client.put(
            f"{API}/connections/llm:groq", json={"api_key": "gsk_test_1234"}
        )
    assert resp.status_code == 200
    conn = resp.json()["connection"]
    assert conn["source"] == "stored"
    assert conn["key_suffix"] == "1234"

    # Delete falls back to env (or none) — idempotent 204.
    assert client.delete(f"{API}/connections/llm:groq").status_code == 204
    refreshed = client.get(f"{API}/connections").json()["connections"]
    groq = next(c for c in refreshed if c["provider"] == "llm:groq")
    assert groq["source"] in ("env", "none")


def test_put_connection_rejects_invalid_key_without_storing(client, vault_key):
    bad = SimpleNamespace(ok=False, detail="That key was rejected (401).")
    with patch("app.api.connections.validate_key", new=AsyncMock(return_value=bad)):
        resp = client.put(
            f"{API}/connections/llm:groq", json={"api_key": "gsk_bad"}
        )
    assert resp.status_code == 400
    groq = next(
        c
        for c in client.get(f"{API}/connections").json()["connections"]
        if c["provider"] == "llm:groq"
    )
    assert groq["source"] != "stored"
