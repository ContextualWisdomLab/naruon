"""add shared email send rate-limit buckets

Revision ID: 0018_email_send_rate_buckets
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_email_send_rate_buckets"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_BUCKET_TABLE = "email_send_rate_buckets"
_EXPIRY_INDEX = "ix_email_send_rate_buckets_expires_at"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_BUCKET_TABLE):
        op.create_table(
            _BUCKET_TABLE,
            sa.Column("bucket_scope_hash", sa.String(length=64), nullable=False),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("bucket_scope_hash"),
        )
    op.create_index(
        _EXPIRY_INDEX,
        _BUCKET_TABLE,
        ["expires_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(_EXPIRY_INDEX, table_name=_BUCKET_TABLE, if_exists=True)
    op.drop_table(_BUCKET_TABLE, if_exists=True)
