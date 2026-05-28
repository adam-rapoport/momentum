"""Unit tests for the Sprint 6 Chunk C model registry."""
from __future__ import annotations

import pytest

from app.core import model_registry
from app.core.model_registry import (
    REGISTRY,
    get_available_models,
    get_model,
    is_model_available,
)


@pytest.fixture(autouse=True)
def both_providers_configured(monkeypatch):
    """Default to both Groq and Google AI Studio being available so each test
    can opt into provider-absence by re-patching the relevant flag."""
    monkeypatch.setattr(model_registry, "_provider_available", lambda p: True)


def test_registry_is_non_empty():
    assert len(REGISTRY) >= 3, "regression: registry should contain >=3 entries"


def test_every_entry_has_a_unique_id():
    ids = [m.id for m in REGISTRY]
    assert len(ids) == len(set(ids))


def test_every_entry_has_valid_role():
    for m in REGISTRY:
        assert m.role in ("light", "heavy", "either"), m


def test_every_entry_has_known_provider():
    for m in REGISTRY:
        assert m.provider in ("groq", "google", "openai"), m


def test_get_available_models_unfiltered_returns_all_when_both_providers_on():
    assert {m.id for m in get_available_models()} == {m.id for m in REGISTRY}


def test_get_available_models_filters_by_role_light():
    light_ids = {m.id for m in get_available_models(role="light")}
    for m in REGISTRY:
        if m.role == "light" or m.role == "either":
            assert m.id in light_ids
        elif m.role == "heavy":
            assert m.id not in light_ids


def test_get_available_models_filters_by_role_heavy():
    heavy_ids = {m.id for m in get_available_models(role="heavy")}
    for m in REGISTRY:
        if m.role == "heavy" or m.role == "either":
            assert m.id in heavy_ids
        elif m.role == "light":
            assert m.id not in heavy_ids


def test_either_role_appears_in_both_filters():
    either_ids = {m.id for m in REGISTRY if m.role == "either"}
    light_ids = {m.id for m in get_available_models(role="light")}
    heavy_ids = {m.id for m in get_available_models(role="heavy")}
    assert either_ids <= light_ids
    assert either_ids <= heavy_ids


def test_is_model_available_true_for_registry_entries():
    for m in REGISTRY:
        assert is_model_available(m.id)


def test_is_model_available_false_for_unknown_id():
    assert not is_model_available("not-a-real-model-id")


def test_is_model_available_respects_role_filter():
    light = next(m for m in REGISTRY if m.role == "light")
    assert is_model_available(light.id, role="light")
    assert not is_model_available(light.id, role="heavy")

    heavy = next(m for m in REGISTRY if m.role == "heavy")
    assert is_model_available(heavy.id, role="heavy")
    assert not is_model_available(heavy.id, role="light")


def test_get_model_returns_entry_by_id():
    first = REGISTRY[0]
    assert get_model(first.id) == first


def test_get_model_returns_none_for_unknown_id():
    assert get_model("not-a-real-model-id") is None


def test_provider_filter_drops_models_when_provider_unconfigured(monkeypatch):
    # Simulate Google not being configured: only Groq entries should remain.
    monkeypatch.setattr(
        model_registry,
        "_provider_available",
        lambda p: p == "groq",
    )
    visible = get_available_models()
    assert all(m.provider == "groq" for m in visible)
    google_entries = [m for m in REGISTRY if m.provider == "google"]
    if google_entries:
        # If the registry has any google entries, they must have been filtered.
        assert len(visible) < len(REGISTRY)
