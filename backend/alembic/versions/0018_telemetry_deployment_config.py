"""Add the encrypted deployment credential for shared telemetry.

Revision ID: 0018_telemetry_deployment_config
Revises: 0017_merge_newsdom_carddav_heads
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_telemetry_deployment_config"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TABLE = "telemetry_deployment_config"
_COLUMNS = {
    "id", "receiver", "bearer_token", "environment", "ca_file", "enabled", "updated_at",
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE):
        if {column["name"] for column in inspector.get_columns(_TABLE)} != _COLUMNS:
            raise RuntimeError("telemetry deployment config table has an incompatible schema")
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receiver", sa.String(length=512), nullable=False),
        sa.Column("bearer_token", sa.String(), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("ca_file", sa.String(length=512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(_TABLE) and {
        column["name"] for column in inspector.get_columns(_TABLE)
    } == _COLUMNS:
        op.drop_table(_TABLE)
