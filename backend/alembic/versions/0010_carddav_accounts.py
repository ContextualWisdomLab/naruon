"""add carddav accounts table

Revision ID: 0010_carddav_accounts
Revises: 0009_project_graph_projection
Create Date: 2026-07-08 00:00:00.000000
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0010_carddav_accounts"
down_revision = "0009_project_graph_projection"

_CARDDAV_TABLE = "carddav_accounts"
_CARDDAV_USER_INDEX = "ix_carddav_accounts_user_id"
_CARDDAV_SOURCE_UID_INDEX = "ix_carddav_accounts_source_uid"
_CARDDAV_ORGANIZATION_INDEX = "ix_carddav_accounts_organization_id"
_CARDDAV_WORKSPACE_INDEX = "ix_carddav_accounts_workspace_id"


def _carddav_table_stub() -> sa.TableClause:
    return sa.table(
        _CARDDAV_TABLE,
        sa.column("account_id", sa.Integer()),
        sa.column("source_uid", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )


def _add_missing_columns(connection) -> None:
    """Bring a previously-seeded table up to the full column contract."""
    inspector = sa.inspect(connection)
    existing = {column["name"] for column in inspector.get_columns(_CARDDAV_TABLE)}
    carddav = _carddav_table_stub()

    if "source_uid" not in existing:
        op.add_column(
            _CARDDAV_TABLE, sa.Column("source_uid", sa.String(), nullable=True)
        )
        rows = connection.execute(
            sa.select(carddav.c.account_id).where(carddav.c.source_uid.is_(None))
        ).fetchall()
        for (account_id,) in rows:
            connection.execute(
                sa.update(carddav)
                .where(carddav.c.account_id == account_id)
                .values(source_uid=f"carddav_src_{uuid.uuid4().hex}")
            )
        op.alter_column(_CARDDAV_TABLE, "source_uid", nullable=False)

    if "organization_id" not in existing:
        op.add_column(
            _CARDDAV_TABLE, sa.Column("organization_id", sa.String(), nullable=True)
        )

    if "workspace_id" not in existing:
        op.add_column(
            _CARDDAV_TABLE, sa.Column("workspace_id", sa.String(), nullable=True)
        )
        connection.execute(
            sa.update(carddav)
            .where(carddav.c.workspace_id.is_(None))
            .values(workspace_id=sa.func.concat("workspace-", carddav.c.user_id))
        )
        op.alter_column(_CARDDAV_TABLE, "workspace_id", nullable=False)

    if "writeback_enabled" not in existing:
        op.add_column(
            _CARDDAV_TABLE,
            sa.Column(
                "writeback_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    created_at = next(
        (
            column
            for column in inspector.get_columns(_CARDDAV_TABLE)
            if column["name"] == "created_at"
        ),
        None,
    )
    if created_at is not None and created_at.get("nullable", True):
        connection.execute(
            sa.update(carddav)
            .where(carddav.c.created_at.is_(None))
            .values(created_at=sa.func.now())
        )
        op.alter_column(
            _CARDDAV_TABLE,
            "created_at",
            nullable=False,
            server_default=sa.func.now(),
        )


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_CARDDAV_TABLE):
        op.create_table(
            _CARDDAV_TABLE,
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("source_uid", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
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
            sa.Column(
                "writeback_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("account_id"),
        )
    else:
        _add_missing_columns(connection)

    op.create_index(
        _CARDDAV_USER_INDEX,
        _CARDDAV_TABLE,
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        _CARDDAV_SOURCE_UID_INDEX,
        _CARDDAV_TABLE,
        ["source_uid"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        _CARDDAV_ORGANIZATION_INDEX,
        _CARDDAV_TABLE,
        ["organization_id"],
        if_not_exists=True,
    )
    op.create_index(
        _CARDDAV_WORKSPACE_INDEX,
        _CARDDAV_TABLE,
        ["workspace_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if inspector.has_table(_CARDDAV_TABLE):
        for index_name in (
            _CARDDAV_WORKSPACE_INDEX,
            _CARDDAV_ORGANIZATION_INDEX,
            _CARDDAV_SOURCE_UID_INDEX,
            _CARDDAV_USER_INDEX,
        ):
            op.drop_index(
                index_name,
                table_name=_CARDDAV_TABLE,
                if_exists=True,
            )
        op.drop_table(_CARDDAV_TABLE)
