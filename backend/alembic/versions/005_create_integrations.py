"""create integrations

Revision ID: 005
Revises: 004
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("encrypted_credentials", sa.LargeBinary, nullable=True),
        sa.Column("scopes", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False, server_default="[]"),
        sa.Column("metadata", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False, server_default="{}"),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_integration_user_provider"),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])
    op.create_index("ix_integrations_provider", "integrations", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_integrations_provider", table_name="integrations")
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
