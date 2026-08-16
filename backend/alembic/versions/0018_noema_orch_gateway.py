"""add noema contextual-orchestrator gateway columns

Revision ID: 0018_noema_orch_gateway
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-16 00:00:00.000000

Noema judgments call only the contextual-orchestrator OpenAI-compatible
gateway. The dedicated inference token and HTTPS ``/v1`` base URL live on
``tenant_configs`` in the Fernet KV (token is EncryptedString). naruon does
not store upstream provider keys for this path.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_noema_orch_gateway"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TENANT_TABLE = "tenant_configs"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_TENANT_TABLE):
        return
    for column in _noema_gateway_columns():
        if not _has_column(inspector, _TENANT_TABLE, column.name):
            op.add_column(_TENANT_TABLE, column)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_TENANT_TABLE):
        return
    for column in reversed(_noema_gateway_columns()):
        if _has_column(inspector, _TENANT_TABLE, column.name):
            op.drop_column(_TENANT_TABLE, column.name)


def _noema_gateway_columns() -> list["sa.Column"]:
    return [
        sa.Column("noema_orchestrator_base_url", sa.String(), nullable=True),
        sa.Column("noema_orchestrator_token", sa.String(), nullable=True),
    ]


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )
