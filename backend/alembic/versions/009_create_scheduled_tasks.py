"""create scheduled_tasks

Revision ID: 009
Revises: 008
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "schedule",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("catch_up_missed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(500), nullable=True),
        sa.Column(
            "last_session_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_scheduled_tasks_project_id", "scheduled_tasks", ["project_id"])
    op.create_index("ix_scheduled_tasks_next_run_at", "scheduled_tasks", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_tasks_next_run_at", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_project_id", table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")
