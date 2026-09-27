"""Store owner-scoped, source-cited events from verified ingest paths.

Revision ID: 0020_source_events
Revises: 0019_personal_reference_address
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_source_events"
down_revision = "0019_personal_reference_address"


def upgrade() -> None:
    op.create_table(
        "source_events",
        sa.Column("event_uid", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("visibility_scope", sa.String(length=24), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_record_uid", sa.String(length=256), nullable=False),
        sa.Column("source_event_key", sa.String(length=256), nullable=False),
        sa.Column(
            "email_id",
            sa.Integer(),
            sa.ForeignKey("email_records.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status_code", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_text", sa.String(length=512), nullable=True),
        sa.Column("source_segment_uids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_source_events_scope_time",
        "source_events",
        ["user_id", "organization_id", "workspace_id", "visibility_scope", "starts_at"],
    )
    op.create_index(
        "ix_source_events_source",
        "source_events",
        ["source_kind", "source_record_uid"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_events_source", table_name="source_events")
    op.drop_index("ix_source_events_scope_time", table_name="source_events")
    op.drop_table("source_events")
