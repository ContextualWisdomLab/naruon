"""add llm batch orchestrator job/item tables and tenant batch config

Revision ID: 0011_llm_batch_orchestrator
Revises: 0010_language_agnostic_search
Create Date: 2026-07-08 00:00:00.000000

Batch-tolerant embeddings route through contextual-orchestrator (the routing /
cost hub), which forwards to pg-llm-batch and records cost. This migration adds
naruon's control-plane audit tables (``llm_batch_jobs`` / ``llm_batch_items``)
and the per-tenant batch config columns on ``tenant_configs``. All new config is
resolved from the Fernet DB at runtime, never from ``os.getenv``.
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_llm_batch_orchestrator"
down_revision = "0010_language_agnostic_search"
branch_labels = None
depends_on = None

_JOBS_TABLE = "llm_batch_jobs"
_ITEMS_TABLE = "llm_batch_items"
_TENANT_TABLE = "tenant_configs"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table(_JOBS_TABLE):
        op.create_table(
            _JOBS_TABLE,
            sa.Column("batch_job_uid", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("job_status", sa.String(), nullable=False),
            sa.Column("routing_mode", sa.String(), nullable=True),
            sa.Column("model_name", sa.String(), nullable=False),
            sa.Column("endpoint_alias", sa.String(), nullable=True),
            sa.Column("orchestrator_batch_uid", sa.String(), nullable=True),
            sa.Column("total_items", sa.Integer(), nullable=False),
            sa.Column("completed_items", sa.Integer(), nullable=False),
            sa.Column("failed_items", sa.Integer(), nullable=False),
            sa.Column("total_tokens", sa.Integer(), nullable=False),
            sa.Column("part_count", sa.Integer(), nullable=False),
            sa.Column("cost_micro_usd", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("batch_job_uid"),
        )

    if not inspector.has_table(_ITEMS_TABLE):
        op.create_table(
            _ITEMS_TABLE,
            sa.Column("batch_item_uid", sa.String(), nullable=False),
            sa.Column("batch_job_uid", sa.String(), nullable=False),
            sa.Column("sequence_no", sa.Integer(), nullable=False),
            sa.Column("part_index", sa.Integer(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("item_status", sa.String(), nullable=False),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["batch_job_uid"],
                [f"{_JOBS_TABLE}.batch_job_uid"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("batch_item_uid"),
        )

    for table_name, index_name, columns in _batch_indexes():
        op.create_index(index_name, table_name, columns, if_not_exists=True)

    if inspector.has_table(_TENANT_TABLE):
        for column in _tenant_batch_columns():
            if not _has_column(inspector, _TENANT_TABLE, column.name):
                op.add_column(_TENANT_TABLE, column)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if inspector.has_table(_TENANT_TABLE):
        for column in reversed(_tenant_batch_columns()):
            if _has_column(inspector, _TENANT_TABLE, column.name):
                op.drop_column(_TENANT_TABLE, column.name)

    for table_name, index_name, _columns in reversed(_batch_indexes()):
        if inspector.has_table(table_name):
            op.drop_index(index_name, table_name=table_name, if_exists=True)

    if inspector.has_table(_ITEMS_TABLE):
        op.drop_table(_ITEMS_TABLE)
    if inspector.has_table(_JOBS_TABLE):
        op.drop_table(_JOBS_TABLE)


def _batch_indexes() -> list[tuple[str, str, list[str]]]:
    return [
        (_JOBS_TABLE, "ix_llm_batch_jobs_organization_id", ["organization_id"]),
        (_JOBS_TABLE, "ix_llm_batch_jobs_user_id", ["user_id"]),
        (_JOBS_TABLE, "ix_llm_batch_jobs_job_status", ["job_status"]),
        (_JOBS_TABLE, "ix_llm_batch_jobs_routing_mode", ["routing_mode"]),
        (
            _JOBS_TABLE,
            "ix_llm_batch_jobs_orchestrator_batch_uid",
            ["orchestrator_batch_uid"],
        ),
        (
            _JOBS_TABLE,
            "ix_llm_batch_jobs_scope_status",
            ["organization_id", "user_id", "job_status"],
        ),
        (_ITEMS_TABLE, "ix_llm_batch_items_batch_job_uid", ["batch_job_uid"]),
        (_ITEMS_TABLE, "ix_llm_batch_items_item_status", ["item_status"]),
        (
            _ITEMS_TABLE,
            "ix_llm_batch_items_job_sequence",
            ["batch_job_uid", "sequence_no"],
        ),
    ]


def _tenant_batch_columns() -> list["sa.Column"]:
    return [
        sa.Column(
            "batch_embedding_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("batch_orchestrator_base_url", sa.String(), nullable=True),
        sa.Column("batch_orchestrator_token", sa.String(), nullable=True),
        sa.Column("batch_orchestrator_endpoint", sa.String(), nullable=True),
        sa.Column("batch_embedding_model", sa.String(), nullable=True),
        sa.Column("batch_local_dsn", sa.String(), nullable=True),
        sa.Column("batch_attribution_service", sa.String(), nullable=True),
        sa.Column("batch_attribution_team", sa.String(), nullable=True),
        sa.Column("batch_attribution_group", sa.String(), nullable=True),
        sa.Column("batch_attribution_company", sa.String(), nullable=True),
    ]


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )
