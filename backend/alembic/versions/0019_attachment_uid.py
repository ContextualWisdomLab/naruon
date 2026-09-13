"""add attachment_uid opaque id to email_attachments

Revision ID: 0019_attachment_uid
Revises: 0018_calendar_conflict_judgments
Create Date: 2026-08-30 00:00:00.000000
"""

from alembic import context, op
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


def _attachment_uid_backfill_statement():
    attachments = _attachment_table_stub()
    return (
        sa.update(attachments)
        .where(attachments.c.attachment_uid.is_(None))
        .values(
            attachment_uid=sa.func.concat(
                "attachment_",
                sa.func.replace(
                    sa.cast(sa.func.gen_random_uuid(), sa.String()),
                    "-",
                    "",
                ),
            )
        )
    )


def _emit_offline_upgrade() -> None:
    op.add_column(
        _ATTACHMENT_TABLE,
        sa.Column("attachment_uid", sa.String(length=96), nullable=True),
    )
    op.execute(_attachment_uid_backfill_statement())
    op.alter_column(_ATTACHMENT_TABLE, "attachment_uid", nullable=False)
    op.create_index(
        _ATTACHMENT_UID_INDEX,
        _ATTACHMENT_TABLE,
        ["attachment_uid"],
        unique=True,
        if_not_exists=True,
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _emit_offline_upgrade()
        return

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
        op.execute(_attachment_uid_backfill_statement())
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


def _emit_offline_downgrade() -> None:
    # A fresh Base.metadata bootstrap can represent the same name as a unique
    # constraint, while Alembic upgrade creates a plain unique index. Offline
    # SQL cannot inspect the catalog, so remove either shape idempotently.
    op.drop_constraint(
        _ATTACHMENT_UID_INDEX,
        _ATTACHMENT_TABLE,
        type_="unique",
        if_exists=True,
    )
    op.drop_index(
        _ATTACHMENT_UID_INDEX,
        table_name=_ATTACHMENT_TABLE,
        if_exists=True,
    )
    op.drop_column(_ATTACHMENT_TABLE, "attachment_uid", if_exists=True)


def downgrade() -> None:
    if context.is_offline_mode():
        _emit_offline_downgrade()
        return

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(_ATTACHMENT_TABLE):
        return

    # A database built by alembic upgrade carries _ATTACHMENT_UID_INDEX as a
    # plain unique index (this file's own upgrade() uses op.create_index), but
    # one bootstrapped fresh via Base.metadata.create_all() (db/models.py's
    # Attachment declares the same name as a table-level UniqueConstraint)
    # carries a constraint-owned index of the identical name instead --
    # PostgreSQL rejects a bare DROP INDEX on that shape, so inspect online
    # and remove the catalog object that actually owns the name.
    unique_constraint_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(_ATTACHMENT_TABLE)
    }
    if _ATTACHMENT_UID_INDEX in unique_constraint_names:
        op.drop_constraint(
            _ATTACHMENT_UID_INDEX,
            _ATTACHMENT_TABLE,
            type_="unique",
            if_exists=True,
        )
    else:
        op.drop_index(
            _ATTACHMENT_UID_INDEX,
            table_name=_ATTACHMENT_TABLE,
            if_exists=True,
        )
    existing_columns = {
        column["name"] for column in inspector.get_columns(_ATTACHMENT_TABLE)
    }
    if "attachment_uid" in existing_columns:
        op.drop_column(_ATTACHMENT_TABLE, "attachment_uid", if_exists=True)
