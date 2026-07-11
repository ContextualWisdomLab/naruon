"""add project graph projection records

Revision ID: 0009_project_graph_projection
Revises: 0008_attachment_parser_audit
Create Date: 2026-07-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_project_graph_projection"
down_revision = "0008_attachment_parser_audit"

_OBJECT_TABLE = "project_graph_objects"
_EDGE_TABLE = "project_graph_edges"
_CORRECTION_TABLE = "project_graph_corrections"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_OBJECT_TABLE):
        op.create_table(
            _OBJECT_TABLE,
            sa.Column("project_graph_object_id", sa.Integer(), nullable=False),
            sa.Column("object_uid", sa.String(length=96), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("email_id", sa.Integer(), nullable=False),
            sa.Column("attachment_id", sa.Integer(), nullable=True),
            sa.Column("primary_content_segment_id", sa.Integer(), nullable=False),
            sa.Column("object_type", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("status_code", sa.String(length=64), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("source_segment_uids", sa.JSON(), nullable=False),
            sa.Column("attributes_json", sa.JSON(), nullable=False),
            sa.Column("extractor_name", sa.String(length=120), nullable=False),
            sa.Column("extractor_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["attachment_id"], ["email_attachments.id"]),
            sa.ForeignKeyConstraint(["email_id"], ["email_records.id"]),
            sa.ForeignKeyConstraint(
                ["primary_content_segment_id"],
                ["content_segments.content_segment_id"],
            ),
            sa.PrimaryKeyConstraint("project_graph_object_id"),
            sa.UniqueConstraint("object_uid", name="uq_project_graph_objects_uid"),
        )

    if not inspector.has_table(_EDGE_TABLE):
        op.create_table(
            _EDGE_TABLE,
            sa.Column("project_graph_edge_id", sa.Integer(), nullable=False),
            sa.Column("edge_uid", sa.String(length=96), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("source_uid", sa.String(length=160), nullable=False),
            sa.Column("target_uid", sa.String(length=160), nullable=False),
            sa.Column("edge_type", sa.String(length=80), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("source_segment_uids", sa.JSON(), nullable=False),
            sa.Column("source_object_id", sa.Integer(), nullable=True),
            sa.Column("target_object_id", sa.Integer(), nullable=True),
            sa.Column("primary_content_segment_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["primary_content_segment_id"],
                ["content_segments.content_segment_id"],
            ),
            sa.ForeignKeyConstraint(
                ["source_object_id"],
                ["project_graph_objects.project_graph_object_id"],
            ),
            sa.ForeignKeyConstraint(
                ["target_object_id"],
                ["project_graph_objects.project_graph_object_id"],
            ),
            sa.PrimaryKeyConstraint("project_graph_edge_id"),
            sa.UniqueConstraint("edge_uid", name="uq_project_graph_edges_uid"),
        )

    if not inspector.has_table(_CORRECTION_TABLE):
        op.create_table(
            _CORRECTION_TABLE,
            sa.Column("project_graph_correction_id", sa.Integer(), nullable=False),
            sa.Column("correction_uid", sa.String(length=96), nullable=False),
            sa.Column("project_graph_object_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("actor_user_id", sa.String(), nullable=False),
            sa.Column("correction_action", sa.String(length=64), nullable=False),
            sa.Column("before_json", sa.JSON(), nullable=False),
            sa.Column("after_json", sa.JSON(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("source_segment_uids", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["project_graph_object_id"],
                ["project_graph_objects.project_graph_object_id"],
            ),
            sa.PrimaryKeyConstraint("project_graph_correction_id"),
            sa.UniqueConstraint(
                "correction_uid",
                name="uq_project_graph_corrections_uid",
            ),
        )

    for table_name, indexes in _project_graph_indexes().items():
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

    for table_name in (_CORRECTION_TABLE, _EDGE_TABLE, _OBJECT_TABLE):
        if inspector.has_table(table_name):
            for index_name, _column_names in reversed(
                _project_graph_indexes()[table_name]
            ):
                op.drop_index(index_name, table_name=table_name, if_exists=True)
            op.drop_table(table_name)


def _project_graph_indexes() -> dict[str, list[tuple[str, list[str]]]]:
    return {
        _OBJECT_TABLE: [
            (
                "ix_project_graph_objects_scope_type_status",
                [
                    "user_id",
                    "organization_id",
                    "workspace_id",
                    "object_type",
                    "status_code",
                ],
            ),
            ("ix_project_graph_objects_email", ["email_id"]),
            ("ix_project_graph_objects_primary_segment", ["primary_content_segment_id"]),
            ("ix_project_graph_objects_extractor", ["extractor_name", "extractor_version"]),
        ],
        _EDGE_TABLE: [
            (
                "ix_project_graph_edges_scope_type",
                ["user_id", "organization_id", "workspace_id", "edge_type"],
            ),
            ("ix_project_graph_edges_source_object", ["source_object_id"]),
            ("ix_project_graph_edges_target_object", ["target_object_id"]),
            ("ix_project_graph_edges_primary_segment", ["primary_content_segment_id"]),
        ],
        _CORRECTION_TABLE: [
            (
                "ix_project_graph_corrections_scope_time",
                ["user_id", "organization_id", "workspace_id", "created_at"],
            ),
            ("ix_project_graph_corrections_object", ["project_graph_object_id"]),
        ],
    }
