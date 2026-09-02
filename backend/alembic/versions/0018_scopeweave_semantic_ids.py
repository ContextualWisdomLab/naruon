"""rename ScopeWeave promotion primary keys semantically

Revision ID: 0018_scopeweave_semantic_ids
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-09-02 05:28:00.000000

The original 0013 migration created generic ``id`` primary-key columns. This
forward migration preserves every row and key value while moving the live
PostgreSQL schema to the bounded-context names used by the ORM. PostgreSQL
column renames are metadata-only but take a brief ACCESS EXCLUSIVE table lock,
so operators should apply the normal Alembic deployment serialization.
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_scopeweave_semantic_ids"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TARGET_TABLE = "scopeweave_promotion_target"
_LINK_TABLE = "scopeweave_promotion_link"


def upgrade() -> None:
    """Rename both ScopeWeave-owned primary-key columns without rewriting rows."""
    op.alter_column(
        _TARGET_TABLE,
        "id",
        new_column_name="scopeweave_promotion_target_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        _LINK_TABLE,
        "id",
        new_column_name="scopeweave_promotion_link_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Restore the historical generic column names for rollback compatibility."""
    op.alter_column(
        _LINK_TABLE,
        "scopeweave_promotion_link_id",
        new_column_name="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        _TARGET_TABLE,
        "scopeweave_promotion_target_id",
        new_column_name="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
