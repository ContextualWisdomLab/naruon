"""add attachment_uid opaque id to email_attachments

Revision ID: 0019_attachment_uid
Revises: 0018_calendar_conflict_judgments
Create Date: 2026-08-30 00:00:00.000000
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0019_attachment_uid"
down_revision = "0018_calendar_conflict_judgments"

_ATTACHMENT_TABLE = "email_attachments"
_ATTACHMENT_UID_INDEX = "uq_email_attachments_uid"


def _attachment_table_stub() -> sa.TableClause:
    return sa.table(
        _ATTACHMENT_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("attachment_uid", sa.String()),
    )


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ATTACHMENT_TABLE):
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(_ATTACHMENT_TABLE)
    }
    if "attachment_uid" not in existing_columns:
        op.add_column(
            _ATTACHMENT_TABLE,
            sa.Column("attachment_uid", sa.String(length=96), nullable=True),
        )
        attachments = _attachment_table_stub()
        rows = connection.execute(
            sa.select(attachments.c.id).where(attachments.c.attachment_uid.is_(None))
        ).fetchall()
        for (attachment_id,) in rows:
            connection.execute(
                sa.update(attachments)
                .where(attachments.c.id == attachment_id)
                .values(attachment_uid=f"attachment_{uuid.uuid4().hex}")
            )
        op.alter_column(_ATTACHMENT_TABLE, "attachment_uid", nullable=False)

    existing_indexes = {
        index["name"] for index in inspector.get_indexes(_ATTACHMENT_TABLE)
    }
    if _ATTACHMENT_UID_INDEX not in existing_indexes:
        op.create_index(
            _ATTACHMENT_UID_INDEX,
            _ATTACHMENT_TABLE,
            ["attachment_uid"],
            unique=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ATTACHMENT_TABLE):
        return

    op.drop_index(_ATTACHMENT_UID_INDEX, table_name=_ATTACHMENT_TABLE, if_exists=True)
    existing_columns = {
        column["name"] for column in inspector.get_columns(_ATTACHMENT_TABLE)
    }
    if "attachment_uid" in existing_columns:
        op.drop_column(_ATTACHMENT_TABLE, "attachment_uid")
