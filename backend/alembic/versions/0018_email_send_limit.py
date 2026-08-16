"""add shared email send limit windows

Revision ID: 0018_email_send_limit
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-16 00:00:00.000000

One current occupancy window per authorized ``(organization_id,
owner_user_id)`` send scope. The table is 3NF: it records only the active
window start and attempt count, never message content or credentials.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_email_send_limit"
down_revision = "0017_merge_newsdom_carddav_heads"

_LIMIT_TABLE = "email_send_limit_windows"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_LIMIT_TABLE):
        op.create_table(
            _LIMIT_TABLE,
            sa.Column("window_uid", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("owner_user_id", sa.String(), nullable=False),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("window_uid"),
            sa.UniqueConstraint(
                "organization_id",
                "owner_user_id",
                name="uq_email_send_limit_windows_scope",
            ),
        )
    for index_name, column_names in _email_send_limit_indexes():
        op.create_index(
            index_name,
            _LIMIT_TABLE,
            column_names,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table(_LIMIT_TABLE):
        for index_name, _column_names in reversed(_email_send_limit_indexes()):
            op.drop_index(
                index_name,
                table_name=_LIMIT_TABLE,
                if_exists=True,
            )
        op.drop_table(_LIMIT_TABLE)


def _email_send_limit_indexes() -> list[tuple[str, list[str]]]:
    return [
        (
            "ix_email_send_limit_windows_scope_time",
            ["organization_id", "owner_user_id", "window_started_at"],
        ),
        ("ix_email_send_limit_windows_organization_id", ["organization_id"]),
        ("ix_email_send_limit_windows_owner_user_id", ["owner_user_id"]),
    ]
