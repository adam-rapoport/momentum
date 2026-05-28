"""Smoke test: per-user API key storage + resolution (C8 Connections).

Walks the resolve → store → resolve → delete → resolve cycle against the
seeded user, proving the stored-key-takes-precedence-over-env behavior and
the clean fallback to env after deletion. Requires Postgres + a seeded user
(`.venv/bin/python -m scripts.seed`) and CREDENTIAL_VAULT_KEY set.

Usage:
  .venv/bin/python -m scripts.try_credentials
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.config import settings
from app.core import credentials
from app.dependencies import SessionLocal
from app.models import User

PROVIDER = "llm:groq"
FAKE_KEY = "gsk_smoketest_0000000000000000000000000000000000000000abcd"


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).order_by(User.created_at).limit(1))
        if user is None:
            print("No seeded user. Run: .venv/bin/python -m scripts.seed")
            return

        env_value = settings.groq_api_key
        print(f"[try_credentials] user={user.email} provider={PROVIDER}")
        print(f"[try_credentials] env GROQ_API_KEY present: {bool(env_value)}\n")

        # 1) Before storing — should resolve to the env value (or None).
        before = await credentials.resolve_api_key(db, user.id, PROVIDER)
        print(f"1. resolve (no stored key) -> {'<env value>' if before == env_value else before}")
        assert before == (env_value or None), "expected env fallback before storing"

        # 2) Store a fake key — resolution should now return it, not env.
        await credentials.store_api_key(db, user.id, PROVIDER, FAKE_KEY)
        stored = await credentials.resolve_api_key(db, user.id, PROVIDER)
        print(f"2. resolve (after store)  -> {stored[:8]}…{stored[-4:]}")
        assert stored == FAKE_KEY, "stored key should take precedence over env"

        # 3) Status view should report source=stored + masked suffix (no secret).
        status = await credentials.get_key_status(db, user.id)
        groq_status = next(s for s in status if s["provider"] == PROVIDER)
        print(f"3. status -> {groq_status}")
        assert groq_status["source"] == "stored"
        assert groq_status["key_suffix"] == FAKE_KEY[-4:]

        # 4) configured_llm_providers should now include 'groq'.
        providers = await credentials.configured_llm_providers(db, user.id)
        print(f"4. configured_llm_providers -> {sorted(providers)}")
        assert "groq" in providers

        # 5) Delete — resolution falls back to env again.
        removed = await credentials.delete_api_key(db, user.id, PROVIDER)
        after = await credentials.resolve_api_key(db, user.id, PROVIDER)
        print(f"5. delete -> {removed}; resolve (after delete) -> "
              f"{'<env value>' if after == env_value else after}")
        assert removed is True
        assert after == (env_value or None), "expected env fallback after delete"

        print("\n[try_credentials] ✓ all assertions passed")


if __name__ == "__main__":
    asyncio.run(main())
