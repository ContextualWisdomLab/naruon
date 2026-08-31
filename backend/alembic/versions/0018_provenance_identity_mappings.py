"""Add scoped portable-to-database provenance identity mappings."""

from alembic import op
import sqlalchemy as sa


revision = "0018_provenance_identity"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provenance_identity_mappings",
        sa.Column("provenance_identity_id", sa.Integer(), primary_key=True),
        sa.Column("target_user_id", sa.String(), nullable=False),
        sa.Column("target_organization_id", sa.String(), nullable=False),
        sa.Column("target_workspace_id", sa.String(), nullable=False),
        sa.Column("source_user_uid", sa.String(length=64), nullable=False),
        sa.Column("source_organization_uid", sa.String(), nullable=False),
        sa.Column("source_workspace_uid", sa.String(), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("portable_uid", sa.String(length=256), nullable=False),
        sa.Column("target_database_uid", sa.String(length=96), nullable=False),
        sa.UniqueConstraint(
            "target_user_id",
            "target_organization_id",
            "target_workspace_id",
            "source_user_uid",
            "source_organization_uid",
            "source_workspace_uid",
            "entity_kind",
            "portable_uid",
            name="uq_provenance_identity_source_target",
        ),
        sa.UniqueConstraint(
            "entity_kind",
            "target_database_uid",
            name="uq_provenance_identity_target_uid",
        ),
    )
    op.create_index(
        "ix_provenance_identity_target_scope",
        "provenance_identity_mappings",
        ["target_user_id", "target_organization_id", "target_workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provenance_identity_target_scope",
        table_name="provenance_identity_mappings",
    )
    op.drop_table("provenance_identity_mappings")
