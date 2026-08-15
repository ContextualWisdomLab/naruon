"""Add normalized object-storage metadata for workspace documents.

Revision ID: 0018_document_object_records
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_document_object_records"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create one-to-one, integrity-bearing document object metadata."""
    op.create_table(
        "document_object_records",
        sa.Column("document_object_record_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("inline_payload", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("content_length", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_state", sa.String(length=32), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "storage_backend = 's3'",
            name="ck_document_object_records_backend",
        ),
        sa.CheckConstraint(
            "storage_state IN ('active', 'consumed', 'deleted')",
            name="ck_document_object_records_state",
        ),
        sa.CheckConstraint(
            "content_length >= 0",
            name="ck_document_object_records_content_length",
        ),
        sa.CheckConstraint(
            "bucket_name IS NOT NULL AND object_key IS NOT NULL "
            "AND inline_payload IS NULL",
            name="ck_document_object_records_s3_locator",
        ),
        sa.CheckConstraint(
            "(storage_state = 'active' AND consumed_at IS NULL "
            "AND deleted_at IS NULL) OR "
            "(storage_state = 'consumed' AND consumed_at IS NOT NULL "
            "AND deleted_at IS NULL) OR "
            "(storage_state = 'deleted' AND consumed_at IS NOT NULL "
            "AND deleted_at IS NOT NULL)",
            name="ck_document_object_records_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["workspace_documents.document_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_object_record_id"),
        sa.UniqueConstraint(
            "document_id",
            name="uq_document_object_records_document",
        ),
        sa.UniqueConstraint(
            "bucket_name",
            "object_key",
            name="uq_document_object_records_locator",
        ),
    )
    op.create_index(
        "ix_document_object_records_state",
        "document_object_records",
        ["storage_backend", "storage_state"],
        unique=False,
    )
    op.create_index(
        "ix_document_object_records_checksum",
        "document_object_records",
        ["checksum_sha256"],
        unique=False,
    )


def downgrade() -> None:
    """Remove document object metadata without deleting external objects."""
    op.drop_index(
        "ix_document_object_records_checksum",
        table_name="document_object_records",
    )
    op.drop_index(
        "ix_document_object_records_state",
        table_name="document_object_records",
    )
    op.drop_table("document_object_records")
