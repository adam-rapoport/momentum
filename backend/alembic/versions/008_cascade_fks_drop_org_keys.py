"""ON DELETE CASCADE on the FK chain + drop organizations.llm_api_keys

Phase 3 item 21 (findings P7/P10): no FK in the schema had any ON DELETE
behavior, so a future hard-delete (e.g. session delete from the sidebar, or
a workspace reset) would orphan child rows or fail outright. Every FK in the
single-workspace chain now cascades:

    organizations <- users <- sessions <- messages
                  <- projects <- sessions
                              <- memory_records
                  (users)     <- integrations

`organizations.llm_api_keys` was a plaintext-key-shaped dead column from the
multi-tenant design — never read or written (keys live Fernet-encrypted in
`integrations`); dropped here.

SQLite can't ALTER a constraint, so the FK changes go through
batch_alter_table (table recreate). The original constraints are unnamed;
the naming_convention below gives the reflected constraints deterministic
names so they can be dropped. Postgres (legacy dev DBs only) uses its
default `<table>_<column>_fkey` names directly.

Revision ID: 008
Revises: 007
Create Date: 2026-06-10
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

# (table, fk column, referenced table) — the whole FK chain.
_FKS: tuple[tuple[str, str, str], ...] = (
    ("users", "organization_id", "organizations"),
    ("projects", "organization_id", "organizations"),
    ("sessions", "user_id", "users"),
    ("sessions", "project_id", "projects"),
    ("messages", "session_id", "sessions"),
    ("memory_records", "project_id", "projects"),
    ("integrations", "user_id", "users"),
)

# Names assigned to the (originally unnamed) reflected FK constraints during
# the SQLite batch recreate, and to the recreated constraints on both dialects.
_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s"}


def _set_ondelete(ondelete: str | None) -> None:
    dialect = op.get_bind().dialect.name
    for table, column, referent in _FKS:
        name = f"fk_{table}_{column}"
        if dialect == "sqlite":
            with op.batch_alter_table(table, naming_convention=_NAMING) as batch:
                batch.drop_constraint(name, type_="foreignkey")
                batch.create_foreign_key(
                    name, referent, [column], ["id"], ondelete=ondelete
                )
        else:
            # First upgrade on Postgres drops the original default-named
            # constraint; after that the convention name applies.
            existing = (
                f"{table}_{column}_fkey" if ondelete is not None else name
            )
            op.drop_constraint(existing, table, type_="foreignkey")
            op.create_foreign_key(
                name, table, referent, [column], ["id"], ondelete=ondelete
            )


def upgrade() -> None:
    _set_ondelete("CASCADE")
    op.drop_column("organizations", "llm_api_keys")


def downgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "llm_api_keys",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )
    _set_ondelete(None)
