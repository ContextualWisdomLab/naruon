"""persist provider-native sync state for DiskSage lineage envelopes

Revision ID: 0019_disksage_provider_sync_state
Revises: 0018_disksage_file_lineage
Create Date: 2026-08-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_disksage_provider_sync_state"
down_revision = "0018_disksage_file_lineage"
branch_labels = None
depends_on = None

_TABLE = "disksage_file_lineage_records"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE) and not any(
        column["name"] == "provider_sync_state"
        for column in inspector.get_columns(_TABLE)
    ):
        op.add_column(
            _TABLE,
            sa.Column(
                "provider_sync_state",
                sa.String(length=32),
                nullable=False,
                server_default="unknown",
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE) and any(
        column["name"] == "provider_sync_state"
        for column in inspector.get_columns(_TABLE)
    ):
        op.drop_column(_TABLE, "provider_sync_state")
