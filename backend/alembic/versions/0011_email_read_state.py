"""Add is_read to emails (IMAP \\Seen read state).

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
_READ_STATE_COLUMN = "is_read"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns(_EMAIL_TABLE)}
    if _READ_STATE_COLUMN not in columns:
        op.add_column(
            _EMAIL_TABLE,
            sa.Column(
                _READ_STATE_COLUMN,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns(_EMAIL_TABLE)}
    if _READ_STATE_COLUMN in columns:
        op.drop_column(_EMAIL_TABLE, _READ_STATE_COLUMN)
