"""align the DiskSage lineage scope index with the list query"""

from alembic import op
import sqlalchemy as sa


revision = "0021_disksage_lineage_scope_index"
down_revision = "0020_disksage_lineage_column_names"
branch_labels = None
depends_on = None

_TABLE = "disksage_file_lineage_records"
_INDEX = "ix_disksage_lineage_scope_time"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_TABLE):
        return
    op.drop_index(_INDEX, table_name=_TABLE, if_exists=True)
    op.create_index(
        _INDEX,
        _TABLE,
        ["user_id", "workspace_id", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_TABLE):
        return
    op.drop_index(_INDEX, table_name=_TABLE, if_exists=True)
    op.create_index(
        _INDEX,
        _TABLE,
        ["user_id", "organization_id", "workspace_id", "created_at"],
        if_not_exists=True,
    )
