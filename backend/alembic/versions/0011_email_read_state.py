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
_OWNERSHIP_TABLE = "email_read_state_ownership"
_OWNERSHIP_KEY_COLUMN = "ownership_key"
_OWNERSHIP_KEY = "0011_email_read_state:email_records:is_read"


def _existing_read_state_column(inspector) -> dict | None:
    return next(
        (
            column
            for column in inspector.get_columns(_EMAIL_TABLE)
            if column["name"] == _READ_STATE_COLUMN
        ),
        None,
    )


def _validate_pre_existing_read_state(column: dict) -> None:
    column_type = column.get("type")
    canonical_shape = (
        isinstance(column_type, sa.Boolean) and column.get("nullable") is False
    )
    if not canonical_shape:
        raise RuntimeError(
            "0011_email_read_state cannot safely use an incompatible "
            f"pre-existing {_EMAIL_TABLE}.{_READ_STATE_COLUMN} column; "
            "reconcile the schema before applying this migration"
        )


def _ownership_record_exists(connection) -> bool:
    ownership_table = sa.table(
        _OWNERSHIP_TABLE,
        sa.column(_OWNERSHIP_KEY_COLUMN, sa.String(length=120)),
    )
    return (
        connection.execute(
            sa.select(ownership_table.c[_OWNERSHIP_KEY_COLUMN])
            .where(
                ownership_table.c[_OWNERSHIP_KEY_COLUMN] == _OWNERSHIP_KEY,
            )
            .limit(1)
        ).first()
        is not None
    )


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE):
        raise RuntimeError(f"required table {_EMAIL_TABLE} is missing")
    if inspector.has_table(_OWNERSHIP_TABLE):
        raise RuntimeError(f"unexpected pre-existing table {_OWNERSHIP_TABLE}")

    existing_column = _existing_read_state_column(inspector)
    owns_read_state_column = existing_column is None
    if owns_read_state_column:
        op.add_column(
            _EMAIL_TABLE,
            sa.Column(
                _READ_STATE_COLUMN,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
    else:
        _validate_pre_existing_read_state(existing_column)

    op.create_table(
        _OWNERSHIP_TABLE,
        sa.Column(_OWNERSHIP_KEY_COLUMN, sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint(
            _OWNERSHIP_KEY_COLUMN,
            name="pk_email_read_state_ownership",
        ),
    )
    ownership_table = sa.table(
        _OWNERSHIP_TABLE,
        sa.column(_OWNERSHIP_KEY_COLUMN, sa.String(length=120)),
    )
    if owns_read_state_column:
        op.bulk_insert(
            ownership_table,
            [{_OWNERSHIP_KEY_COLUMN: _OWNERSHIP_KEY}],
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_OWNERSHIP_TABLE):
        return
    owns_read_state_column = _ownership_record_exists(connection)
    if (
        owns_read_state_column
        and inspector.has_table(_EMAIL_TABLE)
        and _existing_read_state_column(inspector)
    ):
        op.drop_column(_EMAIL_TABLE, _READ_STATE_COLUMN)
    op.drop_table(_OWNERSHIP_TABLE)
