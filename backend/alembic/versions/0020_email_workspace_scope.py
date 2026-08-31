"""add workspace_id scope column to email_records

Revision ID: 0020_email_workspace_scope
Revises: 0019_attachment_uid
Create Date: 2026-08-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_email_workspace_scope"
down_revision = "0019_attachment_uid"

_EMAIL_TABLE = "email_records"
_EMAIL_WORKSPACE_INDEX = "ix_email_records_workspace_id"


def _email_table_stub() -> sa.TableClause:
    return sa.table(
        _EMAIL_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("organization_id", sa.String()),
        sa.column("workspace_id", sa.String()),
    )


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE):
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(_EMAIL_TABLE)
    }
    if "workspace_id" not in existing_columns:
        op.add_column(
            _EMAIL_TABLE, sa.Column("workspace_id", sa.String(), nullable=True)
        )
        emails = _email_table_stub()
        # email_records.organization_id is NOT NULL, so every existing row has
        # a deterministic workspace under this codebase's established
        # convention (services/email_import_service.py, project_graph):
        # workspace-<organization_id>. There is no independent workspace
        # registry to join against -- Email carries no FK to any
        # account/mailbox table that itself has workspace_id (organization
        # config lives in FK-less tenant_configs/caldav_accounts/webdav_accounts).
        connection.execute(
            sa.update(emails)
            .where(emails.c.workspace_id.is_(None))
            .values(
                workspace_id=sa.func.concat("workspace-", emails.c.organization_id)
            )
        )
        op.alter_column(_EMAIL_TABLE, "workspace_id", nullable=False)

    existing_indexes = {
        index["name"] for index in inspector.get_indexes(_EMAIL_TABLE)
    }
    if _EMAIL_WORKSPACE_INDEX not in existing_indexes:
        op.create_index(
            _EMAIL_WORKSPACE_INDEX,
            _EMAIL_TABLE,
            ["workspace_id"],
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_EMAIL_TABLE):
        return

    existing_indexes = {
        index["name"] for index in inspector.get_indexes(_EMAIL_TABLE)
    }
    if _EMAIL_WORKSPACE_INDEX in existing_indexes:
        op.drop_index(
            _EMAIL_WORKSPACE_INDEX, table_name=_EMAIL_TABLE, if_exists=True
        )

    existing_columns = {
        column["name"] for column in inspector.get_columns(_EMAIL_TABLE)
    }
    if "workspace_id" in existing_columns:
        op.drop_column(_EMAIL_TABLE, "workspace_id")
