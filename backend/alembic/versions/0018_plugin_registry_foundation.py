"""Add disabled, tenant-scoped plugin registrations and grants.

Revision ID: 0018_plugin_registry_foundation
Revises: 0017_merge_newsdom_carddav_heads
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_plugin_registry_foundation"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_registrations",
        sa.Column("registration_uid", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("plugin_id", sa.String(128), nullable=False),
        sa.Column("plugin_version", sa.String(64), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "plugin_id",
            "plugin_version",
            name="uq_plugin_registration_scope_version",
        ),
    )
    op.create_index(
        "ix_plugin_registrations_organization_id",
        "plugin_registrations",
        ["organization_id"],
    )
    op.create_index(
        "ix_plugin_registrations_workspace_id", "plugin_registrations", ["workspace_id"]
    )
    op.create_table(
        "plugin_grants",
        sa.Column("grant_uid", sa.String(64), primary_key=True),
        sa.Column(
            "registration_uid",
            sa.String(64),
            sa.ForeignKey("plugin_registrations.registration_uid"),
            nullable=False,
        ),
        sa.Column("granted_capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_plugin_grants_registration_uid", "plugin_grants", ["registration_uid"]
    )


def downgrade() -> None:
    op.drop_table("plugin_grants")
    op.drop_table("plugin_registrations")
