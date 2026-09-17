"""add durable POP3 UIDL observation state

Revision ID: 0019_pop3_observed_uidl
Revises: 0018_email_date_provenance
Create Date: 2026-09-17 00:00:00.000000

Persists RFC 1939 UIDL provider identity per mailbox configuration so bounded
POP3 polling can make progress across reconnects and message-number renumbering.
The UIDL is collection-state identity only; Naruon email Message-ID and source
fingerprints remain the canonical message/deduplication evidence.
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_pop3_observed_uidl"
down_revision = "0018_email_date_provenance"

_TABLE = "pop3_observed_messages"


def upgrade() -> None:
    """Create owner-scoped durable POP3 UIDL observation state if absent."""
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
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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


def downgrade() -> None:
    """Drop durable POP3 UIDL observation state if present."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
