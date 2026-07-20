"""Repair the canonical email read-state column on previously stamped databases.

Revision ID: 0019_email_read_state_repair
Revises: 0018_email_source_lineage
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_email_read_state_repair"
down_revision = "0018_email_source_lineage"
branch_labels = None
depends_on = None

_EMAIL_TABLE = "email_records"
_READ_COLUMN = "is_read"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE) or _has_column(
        inspector, _EMAIL_TABLE, _READ_COLUMN
    ):
        return

    op.add_column(
        _EMAIL_TABLE,
        sa.Column(
            _READ_COLUMN,
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    # This is a compatibility repair for the canonical model. Removing the
    # column would make a stamped database incompatible with the ORM.
    return None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )
