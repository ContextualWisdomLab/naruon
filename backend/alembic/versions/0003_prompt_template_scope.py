"""add prompt template organization and workspace scope

Revision ID: 0003_prompt_template_scope
Revises: 0002_provider_retry_queue
Create Date: 2026-06-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_prompt_template_scope"
down_revision = "0002_provider_retry_queue"
_PROMPT_TABLE = "prompt_templates"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_PROMPT_TABLE):
        return

    column_names = {column["name"] for column in inspector.get_columns(_PROMPT_TABLE)}
    if "prompt_uid" not in column_names:
        op.add_column(_PROMPT_TABLE, sa.Column("prompt_uid", sa.String(), nullable=True))
    if "organization_id" not in column_names:
        op.add_column(
            _PROMPT_TABLE,
            sa.Column("organization_id", sa.String(), nullable=True),
        )
    if "workspace_id" not in column_names:
        op.add_column(
            _PROMPT_TABLE,
            sa.Column("workspace_id", sa.String(), nullable=True),
        )

    op.execute(
        """
        UPDATE prompt_templates
        SET prompt_uid = 'prompt_' || encode(sha256((
            gen_random_uuid()::text || ':' || clock_timestamp()::text || ':' ||
            created_by || ':' || title
        )::bytea), 'hex')
        WHERE prompt_uid IS NULL OR prompt_uid = ''
        """
    )
    op.alter_column(_PROMPT_TABLE, "prompt_uid", nullable=False)

    for index_name, column_names in _prompt_template_indexes():
        op.create_index(index_name, _PROMPT_TABLE, column_names, if_not_exists=True)
    op.create_index(
        "uq_prompt_templates_prompt_uid",
        _PROMPT_TABLE,
        ["prompt_uid"],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_PROMPT_TABLE):
        return

    op.drop_index(
        "uq_prompt_templates_prompt_uid",
        table_name=_PROMPT_TABLE,
        if_exists=True,
    )
    for index_name, _column_names in reversed(_prompt_template_indexes()):
        op.drop_index(index_name, table_name=_PROMPT_TABLE, if_exists=True)

    column_names = {column["name"] for column in inspector.get_columns(_PROMPT_TABLE)}
    for column_name in ("workspace_id", "organization_id", "prompt_uid"):
        if column_name in column_names:
            op.drop_column(_PROMPT_TABLE, column_name)


def _prompt_template_indexes() -> list[tuple[str, list[str]]]:
    return [
        (
            "ix_prompt_templates_owner_scope",
            ["created_by", "organization_id", "workspace_id"],
        ),
        (
            "ix_prompt_templates_shared_scope",
            ["organization_id", "workspace_id", "is_shared"],
        ),
        ("ix_prompt_templates_organization_id", ["organization_id"]),
        ("ix_prompt_templates_workspace_id", ["workspace_id"]),
        ("ix_prompt_templates_prompt_uid", ["prompt_uid"]),
    ]
