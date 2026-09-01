"""Add is_read to email_records (IMAP \\Seen read state).

Existing rows default to read so historical/file imports do not surface as unread.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_email_read_state"
down_revision = "0009_project_graph_projection"
branch_labels = None
depends_on = None

_EMAIL_TABLE = "email_records"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not _has_column(inspector, _EMAIL_TABLE, "is_read"):
        op.add_column(
            _EMAIL_TABLE,
            sa.Column(
                "is_read",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _has_column(inspector, _EMAIL_TABLE, "is_read"):
        op.drop_column(_EMAIL_TABLE, "is_read")


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )
