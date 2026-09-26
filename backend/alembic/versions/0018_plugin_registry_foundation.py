"""Separate plugin identity, release, artifact, registration, and grant.

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
        "plugin_definitions",
        sa.Column("plugin_uid", sa.String(64), primary_key=True),
        sa.Column("plugin_id", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(256), nullable=False),
    )
    op.create_table(
        "plugin_releases",
        sa.Column("release_uid", sa.String(64), primary_key=True),
        sa.Column(
            "plugin_uid",
            sa.String(64),
            sa.ForeignKey("plugin_definitions.plugin_uid"),
            nullable=False,
        ),
        sa.Column("plugin_version", sa.String(64), nullable=False),
        sa.Column("publisher_id", sa.String(128), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "plugin_uid", "plugin_version", name="uq_plugin_release_version"
        ),
    )
    op.create_index("ix_plugin_releases_plugin_uid", "plugin_releases", ["plugin_uid"])
    op.create_table(
        "plugin_artifacts",
        sa.Column("artifact_uid", sa.String(64), primary_key=True),
        sa.Column(
            "release_uid",
            sa.String(64),
            sa.ForeignKey("plugin_releases.release_uid"),
            nullable=False,
        ),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("distribution_uri", sa.String(2048), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "release_uid", "artifact_sha256", name="uq_plugin_artifact_digest"
        ),
    )
    op.create_index(
        "ix_plugin_artifacts_release_uid", "plugin_artifacts", ["release_uid"]
    )
    op.create_table(
        "plugin_registrations",
        sa.Column("registration_uid", sa.String(64), primary_key=True),
        sa.Column(
            "artifact_uid",
            sa.String(64),
            sa.ForeignKey("plugin_artifacts.artifact_uid"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "artifact_uid",
            name="uq_plugin_registration_scope_artifact",
        ),
    )
    op.create_index(
        "ix_plugin_registrations_artifact_uid", "plugin_registrations", ["artifact_uid"]
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
    for table in (
        "plugin_grants",
        "plugin_registrations",
        "plugin_artifacts",
        "plugin_releases",
        "plugin_definitions",
    ):
        op.drop_table(table)
