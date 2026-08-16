"""Add the organization-scoped object-storage provider registry.

Revision ID: 0019_object_storage_providers
Revises: 0018_document_object_records
Create Date: 2026-08-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_object_storage_providers"
down_revision = "0018_document_object_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create normalized provider metadata and encrypted credential columns."""
    op.create_table(
        "object_storage_providers",
        sa.Column("object_storage_provider_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False),
        sa.Column("bucket_name", sa.String(), nullable=False),
        sa.Column("region_name", sa.String(), nullable=False),
        sa.Column("endpoint_url", sa.String(), nullable=True),
        sa.Column("addressing_style", sa.String(), nullable=False),
        sa.Column("access_key_id", sa.String(), nullable=False),
        sa.Column("secret_access_key", sa.String(), nullable=False),
        sa.Column("session_token", sa.String(), nullable=True),
        sa.Column("server_side_encryption", sa.String(), nullable=False),
        sa.Column("kms_key_id", sa.String(), nullable=True),
        sa.Column("expected_bucket_owner", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider_type = 's3'",
            name="ck_object_storage_providers_provider_type",
        ),
        sa.CheckConstraint(
            "addressing_style IN ('virtual', 'path')",
            name="ck_object_storage_providers_addressing_style",
        ),
        sa.CheckConstraint(
            "server_side_encryption IN ('AES256', 'aws:kms')",
            name="ck_object_storage_providers_encryption",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "provider_name",
            name="uq_object_storage_providers_org_name",
        ),
    )
    op.create_index(
        "ix_object_storage_providers_user_id",
        "object_storage_providers",
        ["user_id"],
    )
    op.create_index(
        "ix_object_storage_providers_organization_id",
        "object_storage_providers",
        ["organization_id"],
    )
    op.create_index(
        "ix_object_storage_providers_org_active",
        "object_storage_providers",
        ["organization_id", "is_active", "updated_at"],
    )


def downgrade() -> None:
    """Remove the provider registry without touching stored document metadata."""
    op.drop_index(
        "ix_object_storage_providers_org_active",
        table_name="object_storage_providers",
    )
    op.drop_index(
        "ix_object_storage_providers_organization_id",
        table_name="object_storage_providers",
    )
    op.drop_index(
        "ix_object_storage_providers_user_id",
        table_name="object_storage_providers",
    )
    op.drop_table("object_storage_providers")
