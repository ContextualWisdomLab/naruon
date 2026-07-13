"""add carddav accounts table

Revision ID: 0010_carddav_accounts
Revises: 0009_project_graph_projection
Create Date: 2026-07-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_carddav_accounts"
down_revision = "0009_project_graph_projection"

_CARDDAV_TABLE = "carddav_accounts"
_CARDDAV_USER_INDEX = "ix_carddav_accounts_user_id"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_CARDDAV_TABLE):
        op.create_table(
            _CARDDAV_TABLE,
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("server_url", sa.String(), nullable=False),
            sa.Column("account_username", sa.String(), nullable=False),
            sa.Column("credentials_encrypted", sa.String(), nullable=False),
            sa.Column("discovery_source", sa.String(), nullable=True),
            sa.Column(
                "account_index",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("account_id"),
        )

    op.create_index(
        _CARDDAV_USER_INDEX,
        _CARDDAV_TABLE,
        ["user_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if inspector.has_table(_CARDDAV_TABLE):
        op.drop_index(
            _CARDDAV_USER_INDEX,
            table_name=_CARDDAV_TABLE,
            if_exists=True,
        )
        op.drop_table(_CARDDAV_TABLE)
