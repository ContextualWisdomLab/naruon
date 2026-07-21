"""Add is_read to email_records (IMAP \\Seen read state).

Existing rows default to read so historical/file imports do not surface as
unread.

Originally this revision targeted a legacy ``emails`` table that no migration
or model ever created (see 0011_email_model_reconciliation), which broke
``alembic upgrade head`` on fresh databases. It now targets ``email_records``
— the single email source of truth — and checks for the column first because
fresh databases already receive ``is_read`` from 0001's
``Base.metadata.create_all``.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_email_read_state"
down_revision = "0009_project_graph_projection"
branch_labels = None
depends_on = None

_READ_STATE_TABLE = "email_records"
_READ_STATE_COLUMN = "is_read"


def _existing_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if _READ_STATE_COLUMN in _existing_columns(_READ_STATE_TABLE):
        return
    op.add_column(
        _READ_STATE_TABLE,
        sa.Column(
            _READ_STATE_COLUMN,
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    if _READ_STATE_COLUMN not in _existing_columns(_READ_STATE_TABLE):
        return
    op.drop_column(_READ_STATE_TABLE, _READ_STATE_COLUMN)
