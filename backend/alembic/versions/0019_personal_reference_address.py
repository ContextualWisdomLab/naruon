"""Require an explicit personal address before classifying self-mail.

Revision ID: 0019_personal_reference_address
Revises: 0018_personal_email_references
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_personal_reference_address"
down_revision = "0018_personal_email_references"


def upgrade() -> None:
    op.add_column(
        "tenant_configs",
        sa.Column("personal_reference_address", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_configs", "personal_reference_address")
