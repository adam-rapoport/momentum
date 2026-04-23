"""Smoke test: verify skill detection + Section 15 prompt injection.

Doesn't hit the LLM — just drives the pieces directly:
  - _apply_skill_detection on a fresh Session mutates session_metadata
  - build_prompt emits Section 15 when a skill is active
  - /cancel-skill clears session_metadata
  - keyword triggers activate the right skill

Usage:
  .venv/bin/python -m scripts.try_skills
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.session_engine import _apply_skill_detection
from app.core.system_prompt import _build_skill_section, build_prompt
from app.dependencies import SessionLocal
from app.models import Project, Session, User


async def main() -> None:
    async with SessionLocal() as db:
        user = (await db.scalars(select(User).limit(1))).first()
        project = (await db.scalars(select(Project).limit(1))).first()
        assert user and project, "seed the DB first: python -m scripts.seed"

        # Find or create a detached Session-like object for the test.
        # We don't commit — we just mutate in memory.
        session = (
            await db.scalars(
                select(Session).where(Session.user_id == user.id).limit(1)
            )
        ).first()
        if session is None:
            print("[try_skills] no sessions found; create one via the UI first")
            return

        # Reset metadata for a clean run.
        session.session_metadata = {}

        print("== case 1: slash command activation ==")
        _apply_skill_detection(session, "/write-prd I need a PRD for SSO via Okta")
        print(f"  metadata: {session.session_metadata}")
        assert session.session_metadata.get("active_skill") == "write-prd"
        assert session.session_metadata.get("active_skill_phase") == "intake"

        print("\n== case 2: Section 15 present in prompt ==")
        prompt = await build_prompt(
            db,
            user_id=session.user_id,
            project_id=session.project_id,
            session_metadata=session.session_metadata,
        )
        section_15_present = "## Section 15: Active Skill" in prompt
        workflow_present = "Write-PRD Workflow" in prompt
        print(f"  Section 15 present: {section_15_present}")
        print(f"  Skill body injected: {workflow_present}")
        assert section_15_present and workflow_present

        print("\n== case 3: keyword trigger on fresh session ==")
        session.session_metadata = {}
        _apply_skill_detection(session, "can you write a PRD about referrals?")
        print(f"  metadata: {session.session_metadata}")
        assert session.session_metadata.get("active_skill") == "write-prd"

        print("\n== case 4: keyword ignored while skill active ==")
        # Start with stakeholder-update active
        session.session_metadata = {"active_skill": "stakeholder-update", "active_skill_phase": "audience"}
        _apply_skill_detection(session, "let's write a prd")
        print(f"  metadata: {session.session_metadata}")
        assert session.session_metadata.get("active_skill") == "stakeholder-update"  # unchanged

        print("\n== case 5: slash command overrides active skill ==")
        _apply_skill_detection(session, "/meeting-prep for tomorrow")
        print(f"  metadata: {session.session_metadata}")
        assert session.session_metadata.get("active_skill") == "meeting-prep"
        assert session.session_metadata.get("active_skill_phase") == "context"

        print("\n== case 6: /cancel-skill clears ==")
        _apply_skill_detection(session, "/cancel-skill")
        print(f"  metadata: {session.session_metadata}")
        assert "active_skill" not in session.session_metadata

        print("\n== case 7: no skill -> Section 15 absent ==")
        prompt = await build_prompt(
            db,
            user_id=session.user_id,
            project_id=session.project_id,
            session_metadata={},
        )
        assert "Section 15" not in prompt
        print("  Section 15 correctly absent when no skill is active")

        print("\n== case 8: _build_skill_section handles unknown skill name gracefully ==")
        result = _build_skill_section({"active_skill": "nonexistent-skill"})
        print(f"  result: {result!r}")
        assert result is None

        print("\nAll Chunk B smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
