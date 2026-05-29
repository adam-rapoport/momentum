"""create memory_records

Revision ID: 004
Revises: 003
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False, server_default="[]"),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("search_text", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "type", "slug", name="uq_memory_project_type_slug"),
    )
    op.create_index("ix_memory_records_project_id", "memory_records", ["project_id"])
    op.create_index("ix_memory_records_type", "memory_records", ["type"])


def downgrade() -> None:
    op.drop_index("ix_memory_records_type", table_name="memory_records")
    op.drop_index("ix_memory_records_project_id", table_name="memory_records")
    op.drop_table("memory_records")
