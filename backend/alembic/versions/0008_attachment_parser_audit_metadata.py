"""add attachment parser audit metadata

Revision ID: 0008_attachment_parser_audit_metadata
Revises: 0007_attachment_parse_metadata
Create Date: 2026-07-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_attachment_parser_audit_metadata"
down_revision = "0007_attachment_parse_metadata"

_ATTACHMENT_TABLE = "email_attachments"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ATTACHMENT_TABLE):
        return

    if not _has_column(inspector, _ATTACHMENT_TABLE, "parse_content_type"):
        op.add_column(
            _ATTACHMENT_TABLE,
            sa.Column(
                "parse_content_type",
                sa.String(length=120),
                nullable=False,
                server_default="text/plain",
            ),
        )
    if not _has_column(inspector, _ATTACHMENT_TABLE, "parser_key"):
        op.add_column(
            _ATTACHMENT_TABLE,
            sa.Column(
                "parser_key",
                sa.String(length=64),
                nullable=False,
                server_default="plain_text",
            ),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ATTACHMENT_TABLE):
        return

    for column_name in ("parser_key", "parse_content_type"):
        if _has_column(inspector, _ATTACHMENT_TABLE, column_name):
            op.drop_column(_ATTACHMENT_TABLE, column_name)


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )
