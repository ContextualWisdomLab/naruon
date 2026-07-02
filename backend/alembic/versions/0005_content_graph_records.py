"""add email content graph records

Revision ID: 0005_content_graph_records
Revises: 0004_ai_hub_workflow_runs
Create Date: 2026-07-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_content_graph_records"
down_revision = "0004_ai_hub_workflow_runs"

_NODE_TABLE = "content_nodes"
_SEGMENT_TABLE = "content_segments"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_NODE_TABLE):
        op.create_table(
            _NODE_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("content_node_uid", sa.String(length=64), nullable=False),
            sa.Column("email_id", sa.Integer(), nullable=False),
            sa.Column("attachment_id", sa.Integer(), nullable=True),
            sa.Column("source_kind", sa.String(length=64), nullable=False),
            sa.Column("source_record_uid", sa.String(length=256), nullable=False),
            sa.Column("parent_node_uid", sa.String(length=64), nullable=True),
            sa.Column("node_kind", sa.String(length=64), nullable=False),
            sa.Column("node_path", sa.String(length=512), nullable=False),
            sa.Column("ordinal_index", sa.Integer(), nullable=False),
            sa.Column("display_label", sa.String(length=240), nullable=True),
            sa.Column("safe_text_content", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["attachment_id"], ["email_attachments.id"]),
            sa.ForeignKeyConstraint(["email_id"], ["email_records.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("content_node_uid", name="uq_content_nodes_uid"),
        )

    if not inspector.has_table(_SEGMENT_TABLE):
        op.create_table(
            _SEGMENT_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("content_segment_uid", sa.String(length=64), nullable=False),
            sa.Column("email_id", sa.Integer(), nullable=False),
            sa.Column("attachment_id", sa.Integer(), nullable=True),
            sa.Column("content_node_id", sa.Integer(), nullable=False),
            sa.Column("source_kind", sa.String(length=64), nullable=False),
            sa.Column("source_record_uid", sa.String(length=256), nullable=False),
            sa.Column("segment_kind", sa.String(length=64), nullable=False),
            sa.Column("segment_path", sa.String(length=512), nullable=False),
            sa.Column("ordinal_index", sa.Integer(), nullable=False),
            sa.Column("heading_path", sa.String(length=512), nullable=True),
            sa.Column("safe_text_content", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["attachment_id"], ["email_attachments.id"]),
            sa.ForeignKeyConstraint(["content_node_id"], ["content_nodes.id"]),
            sa.ForeignKeyConstraint(["email_id"], ["email_records.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("content_segment_uid", name="uq_content_segments_uid"),
        )

    for table_name, indexes in _content_graph_indexes().items():
        for index_name, column_names in indexes:
            op.create_index(
                index_name,
                table_name,
                column_names,
                if_not_exists=True,
            )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if inspector.has_table(_SEGMENT_TABLE):
        for index_name, _column_names in reversed(
            _content_graph_indexes()[_SEGMENT_TABLE]
        ):
            op.drop_index(index_name, table_name=_SEGMENT_TABLE, if_exists=True)
        op.drop_table(_SEGMENT_TABLE)

    if inspector.has_table(_NODE_TABLE):
        for index_name, _column_names in reversed(
            _content_graph_indexes()[_NODE_TABLE]
        ):
            op.drop_index(index_name, table_name=_NODE_TABLE, if_exists=True)
        op.drop_table(_NODE_TABLE)


def _content_graph_indexes() -> dict[str, list[tuple[str, list[str]]]]:
    return {
        _NODE_TABLE: [
            (
                "ix_content_nodes_email_source",
                ["email_id", "source_kind", "source_record_uid", "ordinal_index"],
            ),
            ("ix_content_nodes_attachment", ["attachment_id", "ordinal_index"]),
            ("ix_content_nodes_hash", ["content_hash"]),
        ],
        _SEGMENT_TABLE: [
            (
                "ix_content_segments_email_source",
                ["email_id", "source_kind", "source_record_uid", "ordinal_index"],
            ),
            ("ix_content_segments_attachment", ["attachment_id", "ordinal_index"]),
            ("ix_content_segments_node", ["content_node_id"]),
            ("ix_content_segments_hash", ["content_hash"]),
        ],
    }
