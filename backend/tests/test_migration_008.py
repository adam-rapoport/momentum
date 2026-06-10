"""Migration 008 (Phase 3 item 21): CASCADE FKs + drop organizations.llm_api_keys.

SQLite can't alter constraints, so 008 rebuilds tables via batch_alter_table —
exactly the kind of migration that works on a fresh DB but breaks on a
populated one (or vice versa). Both paths are exercised here against real
alembic runs on throwaway SQLite files:

  1. fresh DB: 008 applies as part of `upgrade head`
  2. populated DB: upgrade to 007, insert a full row chain (with
     llm_api_keys), then upgrade to head — data must survive, the dead
     column must be gone, and deleting the organization must cascade
     through every child table.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_upgrade(db_path: Path, revision: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=True,
        cwd=str(_BACKEND_ROOT),
        env=env,
        capture_output=True,
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _fk_on_delete(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    """{fk column: on_delete action} from PRAGMA foreign_key_list."""
    return {
        row[3]: row[6] for row in conn.execute(f"PRAGMA foreign_key_list({table})")
    }


_CASCADING_FKS = {
    "users": ["organization_id"],
    "projects": ["organization_id"],
    "sessions": ["user_id", "project_id"],
    "messages": ["session_id"],
    "memory_records": ["project_id"],
    "integrations": ["user_id"],
}


def _assert_schema_at_head(conn: sqlite3.Connection) -> None:
    assert "llm_api_keys" not in _columns(conn, "organizations")
    for table, fk_cols in _CASCADING_FKS.items():
        actions = _fk_on_delete(conn, table)
        for col in fk_cols:
            assert actions.get(col) == "CASCADE", (
                f"{table}.{col} should be ON DELETE CASCADE, got {actions}"
            )


def test_full_chain_applies_on_fresh_db(tmp_path):
    db_path = tmp_path / "fresh.db"
    _alembic_upgrade(db_path, "head")
    with sqlite3.connect(db_path) as conn:
        _assert_schema_at_head(conn)


def test_008_upgrades_populated_007_db_and_cascades(tmp_path):
    db_path = tmp_path / "populated.db"
    _alembic_upgrade(db_path, "007")

    org, user, project = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    session, message = uuid.uuid4().hex, uuid.uuid4().hex
    memory, integration = uuid.uuid4().hex, uuid.uuid4().hex

    with sqlite3.connect(db_path) as conn:
        # Pre-008 schema still has the dead column.
        assert "llm_api_keys" in _columns(conn, "organizations")
        conn.execute(
            "INSERT INTO organizations (id, name, slug) VALUES (?, ?, ?)",
            (org, "Org", "org"),
        )
        conn.execute(
            "INSERT INTO users (id, email, display_name, auth_provider_id,"
            " organization_id) VALUES (?, ?, ?, ?, ?)",
            (user, "u@example.test", "U", "local", org),
        )
        conn.execute(
            "INSERT INTO projects (id, organization_id, name, slug)"
            " VALUES (?, ?, ?, ?)",
            (project, org, "Default", "default"),
        )
        conn.execute(
            "INSERT INTO sessions (id, user_id, project_id) VALUES (?, ?, ?)",
            (session, user, project),
        )
        conn.execute(
            "INSERT INTO messages (id, session_id, turn_id, seq, role, content)"
            " VALUES (?, ?, 1, 1, 'user', '[]')",
            (message, session),
        )
        conn.execute(
            "INSERT INTO memory_records (id, project_id, type, title, slug,"
            " file_path) VALUES (?, ?, 'decision', 'T', 't', '/tmp/t.md')",
            (memory, project),
        )
        conn.execute(
            "INSERT INTO integrations (id, user_id, provider) VALUES (?, ?, ?)",
            (integration, user, "google"),
        )
        conn.commit()

    _alembic_upgrade(db_path, "head")

    with sqlite3.connect(db_path) as conn:
        _assert_schema_at_head(conn)
        # The batch table-rebuilds preserved every row.
        for table in (
            "organizations", "users", "projects", "sessions",
            "messages", "memory_records", "integrations",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1, table

        # Hard-delete the organization: the whole chain must cascade (P7).
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM organizations WHERE id = ?", (org,))
        conn.commit()
        for table in (
            "users", "projects", "sessions",
            "messages", "memory_records", "integrations",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
