"""rename google_docs provider to google

Sprint 5 unifies the Google integration row so one connection covers
Docs, Gmail, Calendar (and eventually Chat). The row is the same —
we just rename the provider string so new services share credentials
instead of each prompting the user to reconnect.

Existing users with a `google_docs` row get silently upgraded to the
new `google` provider. Their stored scopes still only include Docs +
Drive, so the settings page will show a "Reconnect to enable Gmail +
Calendar" CTA until they re-authorize.

Revision ID: 006
Revises: 005
Create Date: 2026-04-24
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE integrations SET provider = 'google' "
        "WHERE provider = 'google_docs'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE integrations SET provider = 'google_docs' "
        "WHERE provider = 'google'"
    )
