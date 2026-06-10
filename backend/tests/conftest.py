"""Shared fixtures + path setup for pytest.

Layered scope:

- Sprint 4-5 unit tests (model routing rules, concatenated-JSON salvage,
  thought-tag stripper, skill detection, error-handling classification,
  Gmail body parser, Calendar interval math, pending_action staging) —
  pure logic, no DB. They don't depend on any DB fixture below.

- Sprint 6 Chunk D integration tests — talk to a real DB via the
  `db` / `seeded` fixtures.

  Default test DB is a throwaway SQLite file (no service needed), matching
  the desktop build. To run the suite against Postgres instead, set
  `TEST_DATABASE_URL=postgresql+asyncpg://localhost/pmomentum_test`; the
  fixture then probes that DB and `skip`s the integration tests if it's
  unreachable (so `pytest -q` stays green when only running the unit suite).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Make `app.*` importable when pytest is launched from the repo root.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Default: a throwaway SQLite file in the temp dir (no service to install).
# Override with TEST_DATABASE_URL to run the suite against Postgres.
_SQLITE_TEST_PATH = os.path.join(tempfile.gettempdir(), "pmomentum_pytest.db")
DEFAULT_TEST_DB_URL = f"sqlite+aiosqlite:///{_SQLITE_TEST_PATH}"


def _test_db_url() -> str:
    # Empty or unset -> SQLite default (lets CI pass TEST_DATABASE_URL="" to
    # select the SQLite matrix leg).
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DB_URL


# Pin DATABASE_URL to the test DB BEFORE any `app.*` import constructs
# `app.config.settings`. The contract tests (tests/integration/test_ws_contract,
# test_rest_api) run the real app via TestClient, which talks to the engine
# built in app.dependencies from settings.database_url — without this pin it
# would point at ./pmomentum.db (a developer's real local DB) instead of the
# throwaway test database the `db`/`seeded` fixtures migrate and truncate.
os.environ["DATABASE_URL"] = _test_db_url()

# Imports that depend on app.* live below the sys.path + env patch.
from app.models import Base, Organization, Project, User  # noqa: E402


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _reset_sqlite_file(url: str) -> None:
    """Delete any leftover SQLite test file so migrations apply to a clean DB."""
    path = url.split(":///", 1)[1] if ":///" in url else ""
    if path and path != ":memory:" and os.path.exists(path):
        os.remove(path)


def _async_url_to_sync(url: str) -> str:
    """alembic + psycopg-style sync URL needed for migrations and createdb."""
    return url.replace("+asyncpg", "")


def _can_reach_test_db() -> tuple[bool, str]:
    """Best-effort reachability probe so we can skip integration tests
    cleanly when the DB isn't up (rather than spamming failures)."""
    try:
        import psycopg  # type: ignore
    except ImportError as e:
        return False, f"psycopg not installed ({e})"

    parsed = urlparse(_async_url_to_sync(_test_db_url()))
    # Probe the admin `postgres` database, not the test DB — the test DB
    # may not exist yet (we'll CREATE DATABASE in _ensure_test_db_exists).
    try:
        conn = psycopg.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname="postgres",
            connect_timeout=2,
        )
        conn.close()
        return True, ""
    except Exception as e:  # noqa: BLE001 — best-effort probe
        return False, f"{type(e).__name__}: {e}"


def _ensure_test_db_exists() -> None:
    """CREATE DATABASE pmomentum_test if it doesn't already exist."""
    import psycopg  # type: ignore

    parsed = urlparse(_async_url_to_sync(_test_db_url()))
    target_db = parsed.path.lstrip("/")
    if not target_db:
        return

    admin_conn = psycopg.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
        autocommit=True,
    )
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (target_db,)
            )
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{target_db}"')
    finally:
        admin_conn.close()


def _run_alembic_upgrade(test_db_url: str) -> None:
    # alembic/env.py reads DATABASE_URL via pydantic and uses
    # async_engine_from_config — pass the asyncpg URL through unchanged.
    env = {**os.environ, "DATABASE_URL": test_db_url}
    # Use the same Python that's running the tests so we don't depend on
    # `alembic` being on PATH (it usually isn't outside the venv).
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=str(_BACKEND_ROOT),
        env=env,
    )


@pytest.fixture(scope="session")
def _test_db_ready() -> str:
    """One-time per session: prepare the test DB and run migrations. Returns
    the URL. Sync fixture so it runs before any asyncio-scoped fixture spins
    up its own engine.

    SQLite (default): wipe any stale file, then migrate a fresh one.
    Postgres (TEST_DATABASE_URL): probe, create the DB if missing, migrate;
    skip the integration tests cleanly if Postgres isn't reachable."""
    url = _test_db_url()
    if _is_sqlite(url):
        _reset_sqlite_file(url)
        _run_alembic_upgrade(url)
        return url

    reachable, reason = _can_reach_test_db()
    if not reachable:
        pytest.skip(
            f"Test DB unreachable at {url} ({reason}). "
            f"Unset TEST_DATABASE_URL to use SQLite, or start Postgres."
        )
    _ensure_test_db_exists()
    _run_alembic_upgrade(url)
    return url


@pytest_asyncio.fixture
async def test_engine(_test_db_ready: str) -> AsyncIterator:
    """Function-scoped async engine.

    Per-function scope sidesteps pytest-asyncio's loop/pool lifecycle
    headaches with asyncpg (asyncpg connections are bound to the loop
    they were created on, so a session-scoped engine across multiple
    function loops produces "Event loop is closed" on cleanup). The
    expensive bits (createdb + alembic) are still session-scoped via
    `_test_db_ready`. NullPool keeps the per-function setup cheap.
    """
    engine = create_async_engine(
        _test_db_ready, echo=False, poolclass=NullPool
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _truncate_all(engine) -> None:
    """Wipe every data table — leaves alembic's `alembic_version` alone so
    migrations don't re-run between tests."""
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            # SQLite has no TRUNCATE. Delete in reverse dependency order
            # (children before parents) so FK constraints are satisfied.
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
        else:
            table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            await conn.execute(
                text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
            )


@pytest_asyncio.fixture
async def db(test_engine) -> AsyncIterator[AsyncSession]:
    """Function-scoped AsyncSession. After each test, truncates every
    data table so tests stay isolated even when a test commits."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
    await _truncate_all(test_engine)


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> dict:
    """Insert a default Organization, User, and Project — mirrors the
    shape that scripts.seed produces for local dev. Returns a dict so
    integration tests can grab whichever entity they need."""
    org = Organization(
        id=uuid4(),
        name="Test Org",
        slug="test-org",
        plan="free",
        settings={},
    )
    db.add(org)
    await db.flush()

    user = User(
        id=uuid4(),
        email="test@local.dev",
        display_name="Test User",
        auth_provider="local",
        auth_provider_id="local-test",
        organization_id=org.id,
        role="owner",
        preferences={},
    )
    db.add(user)
    await db.flush()

    project = Project(
        id=uuid4(),
        organization_id=org.id,
        name="Default",
        slug="default",
        description="test",
        project_md=None,
        settings={},
        memory_path=None,
    )
    db.add(project)
    await db.flush()
    await db.commit()

    return {"organization": org, "user": user, "project": project}


@pytest.fixture
def client(_test_db_ready: str, tmp_path, monkeypatch):
    """Starlette TestClient against the real `app.main.app`, wired to the
    migrated test DB (see the DATABASE_URL pin at the top of this file).

    Entering the client runs the app lifespan: migrations (a no-op — the
    `_test_db_ready` fixture already brought the schema to head) and the
    default-workspace seed, so `get_default_user` resolves on every request.
    Each test gets a fresh client; all data tables are wiped afterwards so
    contract tests stay isolated from each other and from the `db` fixture.
    """
    from fastapi.testclient import TestClient

    from app.config import settings as app_settings
    from app.main import app

    # Keep memory/document writes triggered through the API out of the repo.
    monkeypatch.setattr(app_settings, "memory_root", str(tmp_path / "memory"))

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(_wipe_all_tables(_test_db_ready))


async def _wipe_all_tables(url: str) -> None:
    """Post-test cleanup for the `client` fixture. Uses its own throwaway
    engine + asyncio.run so it works from sync fixtures regardless of
    pytest-asyncio's loop scoping."""
    engine = create_async_engine(url, echo=False, poolclass=NullPool)
    try:
        await _truncate_all(engine)
    finally:
        await engine.dispose()
