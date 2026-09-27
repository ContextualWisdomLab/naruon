"""Mark verified personal email references for owner-only organization views.

Revision ID: 0018_personal_email_references
Revises: 0017_merge_newsdom_carddav_heads
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_personal_email_references"
down_revision = "0017_merge_newsdom_carddav_heads"


def upgrade() -> None:
    op.add_column(
        "email_records",
        sa.Column("is_personal_reference", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_records", "is_personal_reference")
