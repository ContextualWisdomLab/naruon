"""add scopeweave promotion target and link tables

Revision ID: 0013_scopeweave_promotion
Revises: 0012_llm_batch_orchestrator
Create Date: 2026-07-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_scopeweave_promotion"
down_revision = "0012_llm_batch_orchestrator"

_TARGET_TABLE = "scopeweave_promotion_target"
_LINK_TABLE = "scopeweave_promotion_link"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_TARGET_TABLE):
        op.create_table(
            _TARGET_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("base_url", sa.String(), nullable=False),
            sa.Column("access_token", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "workspace_id",
                name="uq_scopeweave_promotion_target_scope",
            ),
        )

    if not inspector.has_table(_LINK_TABLE):
        op.create_table(
            _LINK_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("project_uid", sa.String(), nullable=False),
            sa.Column("object_uid", sa.String(), nullable=False),
            sa.Column("object_type", sa.String(), nullable=False),
            sa.Column("scopeweave_work_item_id", sa.String(), nullable=False),
            sa.Column("scopeweave_work_item_url", sa.String(), nullable=True),
            sa.Column("promoted_confidence", sa.Float(), nullable=False),
            sa.Column("citation_count", sa.Integer(), nullable=False),
            sa.Column("promoted_by_user_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workspace_id",
                "object_uid",
                name="uq_scopeweave_promotion_link_object",
            ),
        )

    for table_name, indexes in _scopeweave_indexes().items():
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

    for table_name in (_LINK_TABLE, _TARGET_TABLE):
        if inspector.has_table(table_name):
            for index_name, _column_names in reversed(
                _scopeweave_indexes()[table_name]
            ):
                op.drop_index(index_name, table_name=table_name, if_exists=True)
            op.drop_table(table_name)


def _scopeweave_indexes() -> dict[str, list[tuple[str, list[str]]]]:
    return {
        _TARGET_TABLE: [
            ("ix_scopeweave_promotion_target_user", ["user_id"]),
            (
                "ix_scopeweave_promotion_target_scope",
                ["organization_id", "workspace_id"],
            ),
        ],
        _LINK_TABLE: [
            ("ix_scopeweave_promotion_link_user", ["user_id"]),
            ("ix_scopeweave_promotion_link_object_uid", ["object_uid"]),
            ("ix_scopeweave_promotion_link_project", ["project_uid"]),
            (
                "ix_scopeweave_promotion_link_scope",
                ["organization_id", "workspace_id", "project_uid"],
            ),
        ],
    }
