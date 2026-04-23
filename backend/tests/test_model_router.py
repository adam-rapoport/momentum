"""Unit tests for per-turn model routing (Sprint 4 Chunk A).

Mirrors the scenarios in `scripts/try_routing.py` without touching any
external services. No DB, no LLM.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.core.model_router import HEAVY_SLASH_COMMANDS, select_model


@pytest.fixture
def default_model() -> str:
    return settings.groq_model


@pytest.fixture
def heavy_model() -> str:
    return settings.groq_heavy_model


def test_default_and_heavy_models_differ(default_model, heavy_model):
    """If the env points both slots at the same model, routing is a no-op —
    guard against that in config."""
    assert default_model != heavy_model


def test_casual_chat_routes_to_default(default_model):
    assert select_model("hey, what's on the roadmap?", None) == default_model
    assert select_model("thanks, that's all", {}) == default_model


@pytest.mark.parametrize(
    "slash_command",
    sorted(HEAVY_SLASH_COMMANDS),
)
def test_known_slash_commands_route_to_heavy(slash_command, heavy_model):
    text = f"/{slash_command} do the thing please"
    assert select_model(text, {}) == heavy_model


def test_unknown_slash_command_stays_on_default(default_model):
    assert select_model("/something-made-up go", {}) == default_model


def test_active_skill_metadata_forces_heavy(heavy_model):
    # Once a skill is active, every follow-up turn should route to heavy,
    # regardless of what the user typed.
    meta = {"active_skill": "write-prd", "active_skill_phase": "intake"}
    assert select_model("target users are internal admins", meta) == heavy_model
    assert select_model("ok proceed", meta) == heavy_model


def test_no_active_skill_and_plain_text_is_default(default_model):
    assert select_model("hello there", {}) == default_model


def test_empty_input_is_default(default_model):
    assert select_model("", None) == default_model
    assert select_model("   ", None) == default_model


def test_slash_command_is_case_insensitive(heavy_model):
    assert select_model("/WRITE-PRD topic", {}) == heavy_model


def test_none_metadata_is_equivalent_to_empty(default_model, heavy_model):
    # The router accepts None (first-ever turn) and {} (post-clear) — both
    # should behave the same for routing decisions.
    assert select_model("hi", None) == default_model
    assert select_model("/write-prd", None) == heavy_model
