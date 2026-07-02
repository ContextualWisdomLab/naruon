"""add content graph knowledge edges

Revision ID: 0006_knowledge_graph_edges
Revises: 0005_content_graph_records
Create Date: 2026-07-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_knowledge_graph_edges"
down_revision = "0005_content_graph_records"

_EDGE_TABLE = "knowledge_graph_edges"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_EDGE_TABLE):
        op.create_table(
            _EDGE_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("edge_uid", sa.String(length=64), nullable=False),
            sa.Column("email_id", sa.Integer(), nullable=False),
            sa.Column("attachment_id", sa.Integer(), nullable=True),
            sa.Column("source_node_id", sa.Integer(), nullable=True),
            sa.Column("target_node_id", sa.Integer(), nullable=True),
            sa.Column("source_segment_id", sa.Integer(), nullable=True),
            sa.Column("target_segment_id", sa.Integer(), nullable=True),
            sa.Column("source_kind", sa.String(length=64), nullable=False),
            sa.Column("source_record_uid", sa.String(length=256), nullable=False),
            sa.Column("edge_kind", sa.String(length=64), nullable=False),
            sa.Column("edge_path", sa.String(length=512), nullable=False),
            sa.Column("ordinal_index", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["attachment_id"], ["email_attachments.id"]),
            sa.ForeignKeyConstraint(["email_id"], ["email_records.id"]),
            sa.ForeignKeyConstraint(["source_node_id"], ["content_nodes.id"]),
            sa.ForeignKeyConstraint(["target_node_id"], ["content_nodes.id"]),
            sa.ForeignKeyConstraint(["source_segment_id"], ["content_segments.id"]),
            sa.ForeignKeyConstraint(["target_segment_id"], ["content_segments.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("edge_uid", name="uq_knowledge_graph_edges_uid"),
        )

    for index_name, column_names in _knowledge_graph_edge_indexes():
        op.create_index(
            index_name,
            _EDGE_TABLE,
            column_names,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if inspector.has_table(_EDGE_TABLE):
        for index_name, _column_names in reversed(_knowledge_graph_edge_indexes()):
            op.drop_index(index_name, table_name=_EDGE_TABLE, if_exists=True)
        op.drop_table(_EDGE_TABLE)


def _knowledge_graph_edge_indexes() -> list[tuple[str, list[str]]]:
    return [
        (
            "ix_knowledge_graph_edges_email_kind",
            ["email_id", "edge_kind", "ordinal_index"],
        ),
        ("ix_knowledge_graph_edges_attachment", ["attachment_id", "edge_kind"]),
        ("ix_knowledge_graph_edges_source_node", ["source_node_id"]),
        ("ix_knowledge_graph_edges_target_node", ["target_node_id"]),
        ("ix_knowledge_graph_edges_source_segment", ["source_segment_id"]),
        ("ix_knowledge_graph_edges_target_segment", ["target_segment_id"]),
    ]
