"""Unit tests for skill activation + classification (Sprint 3 carry-over).

`detect_skill` decides when to flip a session into a skill workflow based
on the user's message + current metadata. These rules don't hit the DB —
they just operate on strings and the in-memory skills registry loaded
from disk.
"""
from __future__ import annotations

from app.core.skills import CLEAR_SENTINEL, detect_skill, load_skills
from app.core.session_engine import _classify_review_response


def test_skills_loaded_from_disk():
    """Smoke check: make sure the three skills we ship are discoverable."""
    skills = load_skills(force=True)
    assert set(skills.keys()) >= {"write-prd", "stakeholder-update", "meeting-prep"}


def test_slash_command_activates_skill():
    assert detect_skill("/write-prd let's do it", {}) == "write-prd"
    assert detect_skill("/stakeholder-update Q2 rollup", None) == "stakeholder-update"
    assert detect_skill("/meeting-prep Thursday planning", {}) == "meeting-prep"


def test_slash_command_is_case_insensitive():
    assert detect_skill("/WRITE-PRD topic", {}) == "write-prd"


def test_unknown_slash_command_returns_none():
    # Unknown slash commands don't activate anything and don't clear state.
    assert detect_skill("/nonsense please help", {}) is None


def test_cancel_skill_clears_state():
    meta = {"active_skill": "write-prd"}
    assert detect_skill("/cancel-skill", meta) == CLEAR_SENTINEL
    assert detect_skill("/exit-skill", meta) == CLEAR_SENTINEL
    assert detect_skill("/restart", meta) == CLEAR_SENTINEL


def test_keyword_trigger_fires_only_on_fresh_session():
    # With no active skill, a matching keyword should activate.
    assert detect_skill("help me write a prd for onboarding", {}) == "write-prd"


def test_keyword_trigger_ignored_when_skill_already_active():
    # Don't let natural-language mentions of "write a prd" flip sessions
    # that are already mid-workflow.
    meta = {"active_skill": "stakeholder-update"}
    assert detect_skill("I might write a prd later", meta) is None


def test_plain_chat_returns_none():
    assert detect_skill("what do you think?", {}) is None
    assert detect_skill("", {}) is None


def test_slash_command_overrides_active_skill():
    # If a user switches via slash command mid-workflow, we activate the
    # new skill (session_engine._apply_skill_detection then swaps).
    meta = {"active_skill": "write-prd"}
    assert detect_skill("/meeting-prep Thursday", meta) == "meeting-prep"


# --- Pause/review classification (Chunk C Sprint 3) ---

def test_classify_approve_variants():
    assert _classify_review_response("/approve") == "approve"
    assert _classify_review_response("looks good") == "approve"
    assert _classify_review_response("LGTM") == "approve"
    assert _classify_review_response("  approve  ") == "approve"


def test_classify_restart_variants():
    assert _classify_review_response("/restart") == "restart"
    assert _classify_review_response("start over") == "restart"
    assert _classify_review_response("cancel") == "restart"


def test_classify_revise_requires_explicit_prefix():
    # Free-form revisions only land through /revise so the UI doesn't
    # accidentally interpret a follow-up comment as a revision.
    assert _classify_review_response("/revise add a non-goals section") == "revise"
    assert _classify_review_response("/revise") == "revise"


def test_classify_free_text_leaves_pause_in_place():
    assert _classify_review_response("hmm not sure yet") is None
    assert _classify_review_response("") is None
