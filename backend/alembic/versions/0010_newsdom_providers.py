"""add newsdom provider credentials table

Revision ID: 0010_newsdom_providers
Revises: 0009_project_graph_projection
Create Date: 2026-07-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_newsdom_providers"
down_revision = "0009_project_graph_projection"
_NEWSDOM_TABLE = "newsdom_providers"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_NEWSDOM_TABLE):
        op.create_table(
            _NEWSDOM_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("provider_name", sa.String(), nullable=False),
            sa.Column("base_url", sa.String(), nullable=True),
            sa.Column("api_token", sa.String(), nullable=True),
            sa.Column("request_language", sa.String(length=32), nullable=False),
            sa.Column("recognition_mode", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "provider_name",
                name="uq_newsdom_providers_org_name",
            ),
        )

    for index_name, column_names in _newsdom_provider_indexes():
        op.create_index(
            index_name,
            _NEWSDOM_TABLE,
            column_names,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table(_NEWSDOM_TABLE):
        for index_name, _column_names in reversed(_newsdom_provider_indexes()):
            op.drop_index(
                index_name,
                table_name=_NEWSDOM_TABLE,
                if_exists=True,
            )
        op.drop_table(_NEWSDOM_TABLE)


def _newsdom_provider_indexes() -> list[tuple[str, list[str]]]:
    return [
        ("ix_newsdom_providers_user_id", ["user_id"]),
        ("ix_newsdom_providers_organization_id", ["organization_id"]),
        ("ix_newsdom_providers_provider_name", ["provider_name"]),
    ]
