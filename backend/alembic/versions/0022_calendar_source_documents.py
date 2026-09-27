"""Store owner-private iCalendar sources for event evidence.

Revision ID: 0022_calendar_source_documents
Revises: 0021_event_relations
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_calendar_source_documents"
down_revision = "0021_event_relations"


def upgrade() -> None:
    op.create_table(
        "calendar_source_documents",
        sa.Column("document_id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("visibility_scope", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_calendar_source_documents_owner",
        "calendar_source_documents",
        ["user_id", "organization_id", "workspace_id", "created_at"],
    )
    op.add_column(
        "source_events",
        sa.Column("calendar_document_id", sa.String(length=40), nullable=True),
    )
    op.create_foreign_key(
        "fk_source_events_calendar_document",
        "source_events",
        "calendar_source_documents",
        ["calendar_document_id"],
        ["document_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_source_events_calendar_document", "source_events", type_="foreignkey"
    )
    op.drop_column("source_events", "calendar_document_id")
    op.drop_index(
        "ix_calendar_source_documents_owner", table_name="calendar_source_documents"
    )
    op.drop_table("calendar_source_documents")
