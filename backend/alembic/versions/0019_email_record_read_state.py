"""Guard email_records.is_read with NOT NULL DEFAULT true.

Revision ID: 0019_email_record_read_state
Revises: 0018_email_send_rate_buckets

``0011_email_read_state`` only mutates the retired ``emails`` table. Fresh
databases already receive ``email_records.is_read`` from ``0001``
``create_all`` plus the current model ``server_default``. Existing databases
whose ``email_records`` row predates that column (or lacks a server default)
still need a guarded additive revision so raw INSERTs that omit ``is_read``
succeed.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_email_record_read_state"
down_revision = "0018_email_send_rate_buckets"
branch_labels = None
depends_on = None

_EMAIL_RECORDS_TABLE = "email_records"
_READ_STATE_COLUMN = "is_read"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_EMAIL_RECORDS_TABLE):
        return
    columns = {
        column["name"]: column
        for column in inspector.get_columns(_EMAIL_RECORDS_TABLE)
    }
    if _READ_STATE_COLUMN not in columns:
        op.add_column(
            _EMAIL_RECORDS_TABLE,
            sa.Column(
                _READ_STATE_COLUMN,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
        return
    if columns[_READ_STATE_COLUMN].get("default") is None:
        op.alter_column(
            _EMAIL_RECORDS_TABLE,
            _READ_STATE_COLUMN,
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.text("true"),
        )


def downgrade() -> None:
    # No-op: ``create_all`` and later model metadata may already own this
    # column. Dropping it would remove a default this revision did not
    # necessarily create.
    return
