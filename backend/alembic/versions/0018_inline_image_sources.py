"""Store source-linked metadata for base64 images embedded in HTML bodies.

Revision ID: 0018_inline_image_sources
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-21 00:00:00.000000

The table stores the image's original HTML/MIME location, digest, bounded
header facts, and parser outcome. It deliberately does not store base64 or
decoded image bytes. OCR, object labels, captions, and image embeddings remain
separate analysis-run evidence and can be added without changing source
identity or location.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_inline_image_sources"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TABLE_NAME = "image_sources"
_EMAIL_FOREIGN_KEY = "fk_image_sources_email_record_id"
_EMAIL_INDEX = "ix_image_sources_email_ordinal"
_DIGEST_INDEX = "ix_image_sources_content_digest"


def upgrade() -> None:
    """Create the normalized inline-image source table once."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _TABLE_NAME in inspector.get_table_names():
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column("image_source_id", sa.Integer(), primary_key=True),
        sa.Column("image_source_uid", sa.String(length=96), nullable=False),
        sa.Column("email_record_id", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_locator_type", sa.String(length=64), nullable=False),
        sa.Column("source_locator_value", sa.String(length=1024), nullable=False),
        sa.Column("source_ordinal", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("byte_count", sa.BigInteger(), nullable=True),
        sa.Column("content_digest", sa.String(length=64), nullable=True),
        sa.Column("detected_format", sa.String(length=32), nullable=True),
        sa.Column("pixel_width", sa.Integer(), nullable=True),
        sa.Column("pixel_height", sa.Integer(), nullable=True),
        sa.Column("is_animated", sa.Boolean(), nullable=True),
        sa.Column("parse_status", sa.String(length=64), nullable=False),
        sa.Column("parse_error_code", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["email_record_id"],
            ["email_records.id"],
            name=_EMAIL_FOREIGN_KEY,
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("image_source_uid", name="uq_image_sources_uid"),
        sa.UniqueConstraint(
            "email_record_id",
            "source_locator_value",
            name="uq_image_sources_email_locator",
        ),
    )
    op.create_index(
        _EMAIL_INDEX,
        _TABLE_NAME,
        ["email_record_id", "source_ordinal"],
    )
    op.create_index(_DIGEST_INDEX, _TABLE_NAME, ["content_digest"])


def downgrade() -> None:
    """Remove inline-image source evidence while preserving email records."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _TABLE_NAME not in inspector.get_table_names():
        return
    op.drop_index(_DIGEST_INDEX, table_name=_TABLE_NAME)
    op.drop_index(_EMAIL_INDEX, table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
