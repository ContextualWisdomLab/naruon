"""add email media quarantine records

Revision ID: 0018_email_media_quarantine
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-08-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_email_media_quarantine"
down_revision = "0017_merge_newsdom_carddav_heads"

_TABLE = "email_media_quarantine_records"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("quarantine_record_id", sa.Integer(), nullable=False),
            sa.Column("message_record_id", sa.Integer(), nullable=False),
            sa.Column("source_part_index", sa.Integer(), nullable=True),
            sa.Column("content_id_value", sa.String(), nullable=True),
            sa.Column("source_bytes_sha256", sa.String(length=64), nullable=True),
            sa.Column("admission_error_code", sa.String(length=64), nullable=False),
            sa.Column("evidence_boundary_label", sa.String(length=32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["message_record_id"], ["email_records.id"]),
            sa.PrimaryKeyConstraint("quarantine_record_id"),
            sa.UniqueConstraint(
                "message_record_id",
                "source_part_index",
                "source_bytes_sha256",
                name="uq_email_media_quarantine_identity",
            ),
        )

    for index_name, column_names in _quarantine_indexes():
        op.create_index(
            index_name,
            _TABLE,
            column_names,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if inspector.has_table(_TABLE):
        for index_name, _column_names in reversed(_quarantine_indexes()):
            op.drop_index(index_name, table_name=_TABLE, if_exists=True)
        op.drop_table(_TABLE)


def _quarantine_indexes() -> list[tuple[str, list[str]]]:
    return [
        (
            "ix_email_media_quarantine_message_time",
            ["message_record_id", "created_at"],
        ),
        ("ix_email_media_quarantine_records_message_record_id", ["message_record_id"]),
    ]
