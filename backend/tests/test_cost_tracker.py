"""Pricing-table hygiene (Phase 3 item 20, findings A18/A21).

The registry and the pricing table used to drift independently; the first
test pins them together. The rest cover the unknown-model logging behavior
(one warning per process, never per turn) and basic arithmetic.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.core import cost_tracker
from app.core.cost_tracker import GROQ_PRICING, calculate_cost_usd
from app.core.model_registry import REGISTRY


def test_every_registry_model_has_a_pricing_entry():
    missing = [m.id for m in REGISTRY if m.id not in GROQ_PRICING]
    assert not missing, (
        f"registry models without a cost_tracker price entry: {missing} — "
        "their usage would be recorded as $0"
    )


def test_known_model_cost_is_computed():
    # llama-3.1-8b-instant: $0.05 in / $0.08 out per MTok.
    cost = calculate_cost_usd("llama-3.1-8b-instant", 2_000_000, 1_000_000)
    assert cost == Decimal("0.18")


def test_zero_tokens_cost_zero():
    assert calculate_cost_usd("gpt-4o", 0, 0) == Decimal("0")


def test_unknown_model_costs_zero_and_warns_once(caplog):
    cost_tracker._warned_unknown_models.discard("imaginary-model-x")
    with caplog.at_level(logging.WARNING, logger="app.core.cost_tracker"):
        assert calculate_cost_usd("imaginary-model-x", 100, 100) == Decimal("0")
        assert calculate_cost_usd("imaginary-model-x", 100, 100) == Decimal("0")
    warnings = [
        r for r in caplog.records if "imaginary-model-x" in r.getMessage()
    ]
    assert len(warnings) == 1, "unknown model should be logged exactly once"
    cost_tracker._warned_unknown_models.discard("imaginary-model-x")
