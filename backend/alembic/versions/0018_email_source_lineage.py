"""Persist bounded source metadata lineage for imported email records.

Revision ID: 0018_email_source_lineage
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0018_email_source_lineage"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_EMAIL_TABLE = "email_records"
_LINEAGE_COLUMN = "source_lineage_json"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE) or _has_column(
        inspector, _EMAIL_TABLE, _LINEAGE_COLUMN
    ):
        return

    op.add_column(
        _EMAIL_TABLE,
        sa.Column(
            _LINEAGE_COLUMN,
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table(_EMAIL_TABLE) and _has_column(
        inspector, _EMAIL_TABLE, _LINEAGE_COLUMN
    ):
        op.drop_column(_EMAIL_TABLE, _LINEAGE_COLUMN)


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )
