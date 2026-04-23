"""Shared fixtures + path setup for pytest.

Scoped to the Sprint 4 testing goal: lock in the logic we added this sprint
(model routing rules, concatenated-JSON salvage, thought-tag stripper,
skill detection, error-handling classification). DB-integration tests and
full session-engine fixtures are a Sprint 5+ item — see the manual
`scripts/try_*.py` helpers for end-to-end exercise.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `app.*` importable when pytest is launched from the repo root.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
