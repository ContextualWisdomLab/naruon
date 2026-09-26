"""Keep cited calendar dependencies and relation direction.

Revision ID: 0024_event_dependencies
Revises: 0023_event_page_indexes
"""

import sqlalchemy as sa
from alembic import op

revision = "0024_event_dependencies"
down_revision = "0023_event_page_indexes"


def upgrade() -> None:
    op.create_index(
        "ix_source_events_scope_key",
        "source_events",
        [
            "user_id",
            "organization_id",
            "workspace_id",
            "visibility_scope",
            "source_event_key",
        ],
    )
    op.add_column(
        "source_events",
        sa.Column(
            "dependency_evidence", sa.JSON(), nullable=False, server_default="[]"
        ),
    )
    op.add_column("event_relations", sa.Column("enabler_event_uid", sa.String(40)))
    op.create_check_constraint(
        "ck_event_relations_enabler",
        "event_relations",
        "enabler_event_uid IS NULL OR (relation_type = 'enables' AND "
        "enabler_event_uid IN (source_event_uid, target_event_uid))",
    )
    op.add_column(
        "event_relation_corrections",
        sa.Column("before_enabler_event_uid", sa.String(40)),
    )
    op.add_column(
        "event_relation_corrections",
        sa.Column("after_enabler_event_uid", sa.String(40)),
    )


def downgrade() -> None:
    op.drop_column("event_relation_corrections", "after_enabler_event_uid")
    op.drop_column("event_relation_corrections", "before_enabler_event_uid")
    op.drop_constraint("ck_event_relations_enabler", "event_relations", type_="check")
    op.drop_column("event_relations", "enabler_event_uid")
    op.drop_column("source_events", "dependency_evidence")
    op.drop_index("ix_source_events_scope_key", table_name="source_events")
