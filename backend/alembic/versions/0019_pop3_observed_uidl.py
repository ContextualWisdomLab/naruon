"""add durable POP3 UIDL collection progress

Revision ID: 0019_pop3_observed_uidl
Revises: 0018_email_date_provenance
Create Date: 2026-09-17 00:00:00.000000

Persists RFC 1939 UIDL provider identity and bounded retry disposition per
mailbox configuration. Provider state remains collection progress only; Naruon
email Message-ID and source fingerprints remain canonical message/deduplication
evidence.

This revision identifier and parent are branch-local until the canonical
workspace/Alembic owner is integrated; #1195 must rechain this schema after the
then-protected migration head before merge.
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_pop3_observed_uidl"
down_revision = "0018_email_date_provenance"

_TABLE = "pop3_observed_messages"


def upgrade() -> None:
    """Create owner-scoped durable POP3 UIDL collection progress if absent."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _TABLE in inspector.get_table_names():
        return

    op.create_table(
        _TABLE,
        sa.Column("observed_message_id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_config_id",
            sa.Integer(),
            sa.ForeignKey("tenant_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_uidl", sa.String(length=70), nullable=False),
        sa.Column(
            "collection_disposition",
            sa.String(length=16),
            nullable=False,
            server_default="observed",
        ),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_config_id",
            "provider_uidl",
            name="uq_pop3_observed_messages_account_uidl",
        ),
    )
    op.create_index(
        "ix_pop3_observed_messages_account_observed",
        _TABLE,
        ["tenant_config_id", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_pop3_observed_messages_account_retry",
        _TABLE,
        ["tenant_config_id", "collection_disposition", "retry_after"],
        unique=False,
    )


def downgrade() -> None:
    """Drop durable POP3 UIDL collection progress if present."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
