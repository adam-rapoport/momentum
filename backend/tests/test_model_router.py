"""Unit tests for per-turn model routing (Sprint 4 Chunk A).

Mirrors the scenarios in `scripts/try_routing.py` without touching any
external services. No DB, no LLM.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.core.model_router import HEAVY_SLASH_COMMANDS, parse_deep_flag, select_model


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


# ---- Sprint 6 Chunk C: user-preference overrides ---------------------------


def test_user_preference_overrides_light_default_when_available():
    # Llama 3.1 8B Instant is registered as a light model and Groq is the
    # always-available provider, so this should win over the env default.
    prefs = {"light_model": "llama-3.1-8b-instant"}
    assert select_model("hi there", {}, user_preferences=prefs) == "llama-3.1-8b-instant"


def test_user_preference_overrides_heavy_default_for_slash_command():
    # gemini-2.5-pro is registered as heavy. If GOOGLE_AI_API_KEY is set
    # (it is, in our test env), the preference should win.
    prefs = {"heavy_model": "gemini-2.5-pro"}
    chosen = select_model("/write-prd topic", {}, user_preferences=prefs)
    assert chosen == "gemini-2.5-pro"


def test_user_preference_overrides_heavy_default_when_skill_active():
    prefs = {"heavy_model": "gemini-2.5-pro"}
    meta = {"active_skill": "write-prd", "active_skill_phase": "intake"}
    chosen = select_model("ok proceed", meta, user_preferences=prefs)
    assert chosen == "gemini-2.5-pro"


def test_unknown_preference_falls_back_to_env_default(default_model, heavy_model):
    # If a user has a stale preference for a model we removed from the
    # registry (or an outright bogus value), routing must fall back to the
    # env-var default rather than passing the bad ID through.
    bad_prefs_light = {"light_model": "not-a-real-model"}
    bad_prefs_heavy = {"heavy_model": "also-not-real"}
    assert select_model("hi", {}, user_preferences=bad_prefs_light) == default_model
    assert (
        select_model("/write-prd topic", {}, user_preferences=bad_prefs_heavy)
        == heavy_model
    )


def test_role_mismatched_preference_falls_back(default_model, heavy_model):
    # A user who saved a heavy-only model into the light slot (e.g. via
    # API tampering) should fall back, not get the heavy model on light turns.
    prefs = {"light_model": "gemini-2.5-pro"}  # gemini-2.5-pro is heavy-only
    assert select_model("hi", {}, user_preferences=prefs) == default_model


def test_either_role_model_works_in_both_slots():
    prefs = {
        "light_model": "gemini-2.5-flash",
        "heavy_model": "gemini-2.5-flash",
    }
    assert select_model("hi", {}, user_preferences=prefs) == "gemini-2.5-flash"
    assert (
        select_model("/write-prd topic", {}, user_preferences=prefs)
        == "gemini-2.5-flash"
    )


def test_empty_preference_dict_uses_env_defaults(default_model, heavy_model):
    assert select_model("hi", {}, user_preferences={}) == default_model
    assert select_model("/write-prd t", {}, user_preferences={}) == heavy_model


def test_preference_with_empty_string_is_ignored(default_model):
    prefs = {"light_model": ""}
    assert select_model("hi", {}, user_preferences=prefs) == default_model


# ---- Sprint 7 K1: /deep escape-hatch flag ----------------------------------


@pytest.mark.parametrize(
    "raw,expected_clean",
    [
        ("/deep summarize the roadmap", "summarize the roadmap"),
        ("/DEEP shout it", "shout it"),
        ("  /deep   leading space  ", "leading space"),
        ("/deep\nmulti\nline", "multi\nline"),
        ("/deep", ""),  # flag alone -> empty remainder
    ],
)
def test_parse_deep_flag_detects_and_strips(raw, expected_clean):
    is_deep, cleaned = parse_deep_flag(raw)
    assert is_deep is True
    assert cleaned == expected_clean


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "just a normal message",
        "/deepdive into the metrics",  # no space after deep -> not the flag
        "tell me about /deep mode",  # not at the start
        "/write-prd topic",
    ],
)
def test_parse_deep_flag_ignores_non_flag(raw):
    is_deep, cleaned = parse_deep_flag(raw)
    assert is_deep is False
    assert cleaned == raw


def test_deep_flag_routes_to_heavy(heavy_model):
    # A casual message that would normally be light routes heavy with /deep.
    assert select_model("/deep what's on the roadmap?", {}) == heavy_model


def test_deep_flag_routes_heavy_even_with_light_preference(heavy_model):
    # /deep must win over a user's saved light-model preference.
    prefs = {"light_model": "llama-3.1-8b-instant"}
    assert select_model("/deep quick question", {}, user_preferences=prefs) == heavy_model


def test_deepdive_is_not_the_deep_flag(default_model):
    # Guard the word-boundary: /deepdive is an ordinary (unknown) slash word.
    assert select_model("/deepdive into metrics", {}) == default_model


def test_force_heavy_param_routes_heavy(heavy_model):
    # The explicit force_heavy path (how session_engine passes the parsed flag)
    # routes heavy even when the text itself is already clean.
    assert select_model("clean text", {}, force_heavy=True) == heavy_model
