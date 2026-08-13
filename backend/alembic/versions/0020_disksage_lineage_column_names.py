"""rename ambiguous DiskSage lineage column names

Revision ID: 0020_disksage_lineage_column_names
Revises: 0019_disksage_provider_sync_state
Create Date: 2026-08-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_disksage_lineage_column_names"
down_revision = "0019_disksage_provider_sync_state"
branch_labels = None
depends_on = None

_TABLE = "disksage_file_lineage_records"


def _rename_if_present(inspector: sa.Inspector, old: str, new: str) -> None:
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    if old in columns and new not in columns:
        op.alter_column(_TABLE, old, new_column_name=new)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE):
        _rename_if_present(inspector, "bytes", "content_bytes")
        inspector = sa.inspect(op.get_bind())
        _rename_if_present(inspector, "provider", "provider_name")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE):
        _rename_if_present(inspector, "content_bytes", "bytes")
        inspector = sa.inspect(op.get_bind())
        _rename_if_present(inspector, "provider_name", "provider")
