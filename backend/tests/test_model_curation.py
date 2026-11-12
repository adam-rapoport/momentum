"""Picker curation (v0.4.0): the Recommended / Older grouping tables and the
"Newer version available" nudge built on them.

Two kinds of test here. The integrity tests guard the hand-maintained tables
in model_registry (RECOMMENDED, SUPERSEDED_BY) against the mistakes a weekly
roster refresh could make — a typo'd id, a cross-provider link, a loop. The
behaviour tests pin `upgrade_for`, whose one job is to never nudge a user
into a bigger bill.
"""
from __future__ import annotations

import pytest

from app.api import preferences
from app.core import model_registry
from app.core.cost_tracker import GROQ_PRICING, ModelPricing
from app.core.model_registry import (
    RECOMMENDED,
    REGISTRY,
    SUPERSEDED_BY,
    ModelEntry,
    get_model,
    upgrade_for,
)

ALL_PROVIDERS = {"groq", "google", "openai", "anthropic", "openrouter", "mistral"}


# --- table integrity --------------------------------------------------------


def test_curation_tables_only_name_real_registry_models():
    ids = {m.id for m in REGISTRY}
    assert RECOMMENDED <= ids
    assert set(SUPERSEDED_BY) <= ids
    assert set(SUPERSEDED_BY.values()) <= ids


def test_registry_entries_carry_the_table_values():
    for m in REGISTRY:
        assert m.recommended == (m.id in RECOMMENDED)
        assert m.superseded_by == SUPERSEDED_BY.get(m.id)


def test_a_successor_is_always_on_the_same_provider():
    # A nudge must never move someone to a provider they haven't connected.
    for old, new in SUPERSEDED_BY.items():
        assert get_model(old).provider == get_model(new).provider, (old, new)


def test_successor_chains_never_loop():
    for start in SUPERSEDED_BY:
        seen, cur = set(), start
        while cur in SUPERSEDED_BY:
            assert cur not in seen, f"loop through {cur}"
            seen.add(cur)
            cur = SUPERSEDED_BY[cur]


def test_a_recommended_model_is_never_also_an_older_one():
    assert not (RECOMMENDED & set(SUPERSEDED_BY))


def test_every_provider_has_something_recommended():
    for provider in ALL_PROVIDERS:
        assert any(m.recommended for m in REGISTRY if m.provider == provider), provider


def test_every_older_model_still_has_a_current_one_to_fall_back_to():
    # The picker hides older models by default — a provider whose every model
    # were "older" would show an empty dropdown.
    for provider in ALL_PROVIDERS:
        assert any(
            not m.superseded_by for m in REGISTRY if m.provider == provider
        ), provider


# --- upgrade_for, against the real roster ----------------------------------


def test_upgrade_walks_the_chain_to_the_newest_model():
    # Fable 5 -> 5.1 -> 5.2; 5.2 is cheaper than both, so it is the answer
    # from either starting point.
    assert upgrade_for("claude-fable-5", ALL_PROVIDERS).id == "claude-fable-5-2"
    assert upgrade_for("claude-fable-5-1", ALL_PROVIDERS).id == "claude-fable-5-2"


def test_same_price_successor_is_offered():
    assert upgrade_for("claude-sonnet-5", ALL_PROVIDERS).id == "claude-sonnet-5-5"


def test_current_generation_models_get_no_nudge():
    for model_id in ("claude-fable-5-2", "gemini-3.8-flash", "gpt-6.1-sol", "mistral-large-4"):
        assert upgrade_for(model_id, ALL_PROVIDERS) is None


def test_no_nudge_without_the_successors_provider_connected():
    assert upgrade_for("claude-sonnet-5", {"google"}) is None


def test_unknown_or_dynamic_models_get_no_nudge():
    assert upgrade_for("not-a-real-model", ALL_PROVIDERS) is None
    assert upgrade_for("ollama:llama3.1:8b", ALL_PROVIDERS) is None


def test_every_nudge_the_real_roster_produces_is_same_price_or_cheaper():
    """The promise to the user, checked across the whole live roster: a nudge
    never points at something that costs more on input OR output."""
    nudges = 0
    for m in REGISTRY:
        target = upgrade_for(m.id, ALL_PROVIDERS)
        if target is None:
            continue
        nudges += 1
        old, new = GROQ_PRICING[m.id], GROQ_PRICING[target.id]
        assert new.input <= old.input and new.output <= old.output, (m.id, target.id)
        assert target.provider == m.provider
        assert not target.superseded_by or upgrade_for(target.id, ALL_PROVIDERS) is None
    assert nudges > 0  # the tables are doing something


# --- upgrade_for, against a tiny synthetic roster ---------------------------


def _entry(model_id: str, superseded_by: str | None = None) -> ModelEntry:
    return ModelEntry(
        id=model_id, provider="openai", display_name=model_id.upper(),
        role="either", superseded_by=superseded_by,
    )


@pytest.fixture
def fake_roster(monkeypatch):
    def install(entries: list[ModelEntry], prices: dict[str, tuple[str, str]]):
        monkeypatch.setattr(model_registry, "REGISTRY", tuple(entries))
        monkeypatch.setattr(
            model_registry, "GROQ_PRICING",
            {k: ModelPricing(*v) for k, v in prices.items()},
        )
    return install


def test_pricier_successor_is_never_offered(fake_roster):
    fake_roster(
        [_entry("a", "b"), _entry("b")],
        {"a": ("1.00", "5.00"), "b": ("1.00", "5.01")},  # one cent dearer out
    )
    assert upgrade_for("a", {"openai"}) is None


def test_cheaper_input_does_not_excuse_dearer_output(fake_roster):
    # The lopsided OpenRouter pattern: far cheaper to read with, dearer to
    # answer with. Not an upgrade for someone who writes long documents.
    fake_roster(
        [_entry("a", "b"), _entry("b")],
        {"a": ("1.00", "5.00"), "b": ("0.01", "9.00")},
    )
    assert upgrade_for("a", {"openai"}) is None


def test_falls_back_to_an_earlier_link_when_the_newest_costs_more(fake_roster):
    fake_roster(
        [_entry("a", "b"), _entry("b", "c"), _entry("c")],
        {"a": ("2.00", "10.00"), "b": ("2.00", "10.00"), "c": ("3.00", "15.00")},
    )
    assert upgrade_for("a", {"openai"}).id == "b"


def test_skips_a_pricey_middle_link_to_reach_a_cheaper_newest(fake_roster):
    fake_roster(
        [_entry("a", "b"), _entry("b", "c"), _entry("c")],
        {"a": ("2.00", "10.00"), "b": ("5.00", "30.00"), "c": ("2.00", "10.00")},
    )
    assert upgrade_for("a", {"openai"}).id == "c"


def test_unpriced_models_are_left_alone(fake_roster):
    fake_roster([_entry("a", "b"), _entry("b")], {"b": ("1.00", "5.00")})
    assert upgrade_for("a", {"openai"}) is None  # can't compare -> say nothing
    fake_roster([_entry("a", "b"), _entry("b")], {"a": ("1.00", "5.00")})
    assert upgrade_for("a", {"openai"}) is None


def test_a_looping_table_cannot_hang_the_app(fake_roster):
    fake_roster(
        [_entry("a", "b"), _entry("b", "a")],
        {"a": ("1.00", "5.00"), "b": ("1.00", "5.00")},
    )
    assert upgrade_for("a", {"openai"}).id == "b"  # terminates, sensibly


def test_dangling_successor_id_is_ignored(fake_roster):
    fake_roster([_entry("a", "gone")], {"a": ("1.00", "5.00")})
    assert upgrade_for("a", {"openai"}) is None


# --- what the Settings screen is served --------------------------------------


def test_picker_models_carry_grouping_flags_and_prices():
    view = preferences._public_view({}, ALL_PROVIDERS)
    by_id = {m["id"]: m for m in view["available_light_models"]}
    sonnet = by_id["claude-sonnet-5-5"]
    assert sonnet["recommended"] is True and sonnet["superseded_by"] is None
    assert (sonnet["input_per_mtok"], sonnet["output_per_mtok"]) == ("2.00", "10.00")
    assert by_id["claude-sonnet-5"]["superseded_by"] == "claude-sonnet-5-5"
    # The unfiltered list the first-run wizard uses gets the same fields.
    assert all("input_per_mtok" in m for m in view["registry_models"])


def test_view_offers_an_upgrade_for_an_older_pick():
    view = preferences._public_view(
        {"light_model": "claude-haiku-4-5", "heavy_model": "claude-sonnet-5"},
        ALL_PROVIDERS,
    )
    assert view["light_upgrade"] == {
        "from_id": "claude-haiku-4-5",
        "to_id": "claude-haiku-5-5",
        "to_name": "Claude Haiku 5.5 (Anthropic)",
        "cheaper": True,
    }
    assert view["heavy_upgrade"]["to_id"] == "claude-sonnet-5-5"
    assert view["heavy_upgrade"]["cheaper"] is False  # same price exactly


def test_view_offers_nothing_for_current_picks():
    view = preferences._public_view(
        {"light_model": "claude-haiku-5-5", "heavy_model": "claude-sonnet-5-5"},
        ALL_PROVIDERS,
    )
    assert view["light_upgrade"] is None and view["heavy_upgrade"] is None
