"""Index owner-scoped event candidate and relation pages.

Revision ID: 0023_event_page_indexes
Revises: 0022_calendar_source_documents
"""

from alembic import op

revision = "0023_event_page_indexes"
down_revision = "0022_calendar_source_documents"


def upgrade() -> None:
    op.create_index(
        "ix_source_events_scope_end",
        "source_events",
        ["user_id", "organization_id", "workspace_id", "visibility_scope", "ends_at"],
    )
    op.create_index(
        "ix_source_events_scope_uid",
        "source_events",
        ["user_id", "organization_id", "workspace_id", "visibility_scope", "event_uid"],
    )
    op.drop_index("ix_event_relations_scope", table_name="event_relations")
    op.create_index(
        "ix_event_relations_scope_uid",
        "event_relations",
        [
            "user_id",
            "organization_id",
            "workspace_id",
            "visibility_scope",
            "relation_uid",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_event_relations_scope_uid", table_name="event_relations")
    op.create_index(
        "ix_event_relations_scope",
        "event_relations",
        ["user_id", "organization_id", "workspace_id", "visibility_scope"],
    )
    op.drop_index("ix_source_events_scope_end", table_name="source_events")
    op.drop_index("ix_source_events_scope_uid", table_name="source_events")
