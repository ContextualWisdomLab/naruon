"""Store scoped event relations and human corrections.

Revision ID: 0021_event_relations
Revises: 0020_source_events
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_event_relations"
down_revision = "0020_source_events"


def upgrade() -> None:
    op.create_table(
        "event_relations",
        sa.Column("relation_uid", sa.String(length=40), primary_key=True),
        sa.Column("source_event_uid", sa.String(length=40), nullable=False),
        sa.Column("target_event_uid", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("visibility_scope", sa.String(length=24), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_code", sa.String(length=64), nullable=False),
        sa.Column("source_segment_uids", sa.JSON(), nullable=False),
        sa.Column("corrected_by_user_id", sa.String(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_event_uid"], ["source_events.event_uid"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_event_uid"], ["source_events.event_uid"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "source_event_uid < target_event_uid", name="ck_event_relations_order"
        ),
        sa.CheckConstraint(
            "relation_type IN ('candidate', 'enables', 'conflicts', 'unrelated')",
            name="ck_event_relations_type",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_event_relations_confidence"
        ),
        sa.UniqueConstraint(
            "source_event_uid", "target_event_uid", name="uq_event_relations_pair"
        ),
    )
    op.create_index(
        "ix_event_relations_scope",
        "event_relations",
        ["user_id", "organization_id", "workspace_id", "visibility_scope"],
    )
    op.create_table(
        "event_relation_corrections",
        sa.Column("correction_uid", sa.String(length=40), primary_key=True),
        sa.Column("relation_uid", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("before_type", sa.String(length=16), nullable=False),
        sa.Column("after_type", sa.String(length=16), nullable=False),
        sa.Column("source_segment_uids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["relation_uid"], ["event_relations.relation_uid"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_event_relation_corrections_relation",
        "event_relation_corrections",
        ["relation_uid"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_relation_corrections_relation",
        table_name="event_relation_corrections",
    )
    op.drop_table("event_relation_corrections")
    op.drop_index("ix_event_relations_scope", table_name="event_relations")
    op.drop_table("event_relations")
