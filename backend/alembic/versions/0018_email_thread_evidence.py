"""Persist owner-scoped email reply evidence and correction state.

Revision ID: 0018_email_thread_evidence
Revises: 0017_merge_newsdom_carddav_heads
"""

import datetime
import re

from alembic import op
import sqlalchemy as sa

revision = "0018_email_thread_evidence"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TABLE = "email_thread_evidence"
_BRACKETED = re.compile(r"<([^>]+)>")
_CANONICAL_INDEX = "ix_email_records_owner_canonical_message_id"


def _target_ids(raw: str) -> list[str | None]:
    if len(raw) > 8192:
        return [None]
    tokens = _BRACKETED.findall(raw) or raw.split()
    ids = list(
        dict.fromkeys(
            value for token in tokens if (value := "".join(token.strip("<>").split()))
        )
    )
    if not ids or len(ids) > 64 or any(len(value) > 512 for value in ids):
        return [None]
    return ids


def upgrade() -> None:
    connection = op.get_bind()
    message_id = sa.column("message_id", sa.String())
    canonical_id = message_id
    for whitespace in (" ", "\t", "\r", "\n", "\v", "\f"):
        canonical_id = sa.func.replace(
            canonical_id, sa.literal_column(f"'{whitespace}'"), sa.literal_column("''")
        )
    op.create_index(
        _CANONICAL_INDEX,
        "email_records",
        ["user_id", "organization_id", sa.func.trim(canonical_id, sa.literal_column("'<>'"))],
        if_not_exists=True,
    )
    if not sa.inspect(connection).has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_email_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("source_message_id", sa.String(), nullable=False),
            sa.Column("target_message_id", sa.String(length=512), nullable=True),
            sa.Column("evidence_source", sa.String(length=16), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("incomplete", sa.Boolean(), nullable=False),
            sa.Column("detached_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("detached_by", sa.String(), nullable=True),
            sa.Column("detach_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["source_email_id"], ["email_records.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint(
                "source_email_id",
                "evidence_source",
                "ordinal",
                name="uq_email_thread_evidence_source_ordinal",
            ),
        )
    op.create_index(
        "ix_email_thread_evidence_source_email_id",
        _TABLE,
        ["source_email_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_email_thread_evidence_owner_target",
        _TABLE,
        ["user_id", "organization_id", "target_message_id"],
        if_not_exists=True,
    )

    emails = sa.table(
        "email_records",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.String()),
        sa.column("organization_id", sa.String()),
        sa.column("message_id", sa.String()),
        sa.column("in_reply_to", sa.String()),
        sa.column("references", sa.String()),
    )
    evidence = sa.table(
        _TABLE,
        *(
            sa.column(name, kind)
            for name, kind in (
                ("source_email_id", sa.Integer()),
                ("user_id", sa.String()),
                ("organization_id", sa.String()),
                ("source_message_id", sa.String()),
                ("target_message_id", sa.String()),
                ("evidence_source", sa.String()),
                ("ordinal", sa.Integer()),
                ("incomplete", sa.Boolean()),
                ("created_at", sa.DateTime(timezone=True)),
            )
        ),
    )
    last_id = 0
    while True:
        rows = (
            connection.execute(
                sa.select(emails)
                .where(emails.c.id > last_id)
                .order_by(emails.c.id)
                .limit(500)
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        existing_sources = set(
            connection.execute(
                sa.select(evidence.c.source_email_id).where(
                    evidence.c.source_email_id.in_([row["id"] for row in rows])
                )
            ).scalars()
        )
        values = []
        for email in rows:
            if email["id"] in existing_sources:
                continue
            for source in ("in_reply_to", "references"):
                raw = email[source]
                if not raw:
                    continue
                for ordinal, target in enumerate(_target_ids(raw)):
                    values.append(
                        {
                            "source_email_id": email["id"],
                            "user_id": email["user_id"],
                            "organization_id": email["organization_id"],
                            "source_message_id": email["message_id"],
                            "target_message_id": target,
                            "evidence_source": source,
                            "ordinal": ordinal,
                            "incomplete": target is None,
                            "created_at": datetime.datetime.now(datetime.timezone.utc),
                        }
                    )
        if values:
            connection.execute(sa.insert(evidence), values)
        last_id = rows[-1]["id"]


def downgrade() -> None:
    op.drop_index(_CANONICAL_INDEX, table_name="email_records")
    op.drop_index("ix_email_thread_evidence_owner_target", table_name=_TABLE)
    op.drop_index("ix_email_thread_evidence_source_email_id", table_name=_TABLE)
    op.drop_table(_TABLE)
