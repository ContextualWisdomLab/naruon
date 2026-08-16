"""Add durable object-storage orphan cleanup records.

Revision ID: 0020_object_storage_cleanup_records
Revises: 0019_object_storage_providers
Create Date: 2026-08-16 19:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_object_storage_cleanup_records"
down_revision = "0019_object_storage_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create provider-bound retry rows for failed S3 compensation deletes."""
    op.create_table(
        "object_storage_cleanup_records",
        sa.Column("object_storage_cleanup_record_id", sa.Integer(), primary_key=True),
        sa.Column("object_storage_provider_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("bucket_name", sa.String(), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("content_length", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("cleanup_reason", sa.String(), nullable=False),
        sa.Column("cleanup_status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_length >= 0",
            name="ck_object_storage_cleanup_records_content_length",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_object_storage_cleanup_records_attempt_count",
        ),
        sa.CheckConstraint(
            "cleanup_status IN ('pending', 'completed')",
            name="ck_object_storage_cleanup_records_status",
        ),
        sa.ForeignKeyConstraint(
            ["object_storage_provider_id"],
            ["object_storage_providers.object_storage_provider_id"],
            name="fk_object_storage_cleanup_records_provider",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "object_storage_provider_id",
            "bucket_name",
            "object_key",
            name="uq_object_storage_cleanup_records_locator",
        ),
    )
    op.create_index(
        "ix_object_storage_cleanup_records_organization_id",
        "object_storage_cleanup_records",
        ["organization_id"],
    )
    op.create_index(
        "ix_object_storage_cleanup_records_status_created",
        "object_storage_cleanup_records",
        ["cleanup_status", "created_at"],
    )


def downgrade() -> None:
    """Remove orphan cleanup retry records without altering stored objects."""
    op.drop_index(
        "ix_object_storage_cleanup_records_status_created",
        table_name="object_storage_cleanup_records",
    )
    op.drop_index(
        "ix_object_storage_cleanup_records_organization_id",
        table_name="object_storage_cleanup_records",
    )
    op.drop_table("object_storage_cleanup_records")
