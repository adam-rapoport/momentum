"""add messages.seq — explicit intra-session ordering

Messages within a turn were ordered by created_at, whose SQLite resolution is
one second: every message persisted in a tool batch ties, and the relative
order of an assistant tool_use message and its tool results was rowid luck.
One wrong sort produces an invalid provider history (tool result before the
call) and the provider rejects every subsequent turn. `seq` is a per-session
monotonic counter assigned by the session engine; ordering is
(turn_id, seq).

Backfill: SQLite rowid is monotonic in insertion order, which is exactly the
order messages were created in, so seq=rowid preserves history. On Postgres
(legacy dev DBs) a window function over the old sort keys does the same.

Revision ID: 007
Revises: 006
Create Date: 2026-06-09
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("seq", sa.Integer(), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("UPDATE messages SET seq = rowid")
    else:
        op.execute(
            """
            UPDATE messages SET seq = sub.rn
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY session_id
                           ORDER BY turn_id, created_at, id
                       ) AS rn
                FROM messages
            ) AS sub
            WHERE messages.id = sub.id
            """
        )
    op.create_index("ix_messages_session_seq", "messages", ["session_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_messages_session_seq", table_name="messages")
    op.drop_column("messages", "seq")
