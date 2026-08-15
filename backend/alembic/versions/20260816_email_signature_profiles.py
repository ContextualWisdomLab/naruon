"""Add normalized outbound email signature profiles.

Revision ID: 20260816_email_signature_profiles
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-16 03:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_email_signature_profiles"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create one normalized plain-text signature profile per mailbox scope."""
    op.create_table(
        "email_signature_profiles",
        sa.Column("email_signature_profile_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("signature_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email_signature_profile_id"),
    )
    op.create_index(
        "ix_email_signature_profiles_user_id",
        "email_signature_profiles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_signature_profiles_organization_id",
        "email_signature_profiles",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_email_signature_profiles_owner_scope",
        "email_signature_profiles",
        ["user_id", sa.text("COALESCE(organization_id, '')")],
        unique=True,
    )


def downgrade() -> None:
    """Remove outbound signature profiles without touching mailbox settings."""
    op.drop_index(
        "uq_email_signature_profiles_owner_scope",
        table_name="email_signature_profiles",
    )
    op.drop_index(
        "ix_email_signature_profiles_organization_id",
        table_name="email_signature_profiles",
    )
    op.drop_index(
        "ix_email_signature_profiles_user_id",
        table_name="email_signature_profiles",
    )
    op.drop_table("email_signature_profiles")
