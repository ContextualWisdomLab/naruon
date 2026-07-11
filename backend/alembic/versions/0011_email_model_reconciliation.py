"""email model reconciliation (single source of truth)

Drops the abandoned parallel account-centric email model tables:
user_accounts, provider_accounts, email_raws, email_messages,
email_instances, email_threads, email_thread_edges.

No alembic revision ever created these tables and bootstrap_db does
not create them either — they only materialized in development and
test databases through ``Base.metadata.create_all`` while their ORM
classes still existed. The upgrade is therefore a defensive,
dev-database-only cleanup; managed databases are unaffected.

``email_records`` (+ fingerprint dedup + threading_service) remains
the single email source of truth; account/provider configuration
lives in tenant_configs, caldav_accounts, and webdav_accounts. See
docs/engineering/email-model-reconciliation.md.

Revision ID: 0011_email_model_reconciliation
Revises: 0010_language_agnostic_search
Create Date: 2026-07-11 00:00:00.000000
"""

from alembic import op
from sqlalchemy import text

revision = "0011_email_model_reconciliation"
down_revision = "0010_language_agnostic_search"

# Ordered so foreign-key dependents drop before their targets.
_RETIRED_TABLE_DROP_STATEMENTS = (
    "DROP TABLE IF EXISTS email_thread_edges",
    "DROP TABLE IF EXISTS email_instances",
    "DROP TABLE IF EXISTS email_raws",
    "DROP TABLE IF EXISTS email_messages",
    "DROP TABLE IF EXISTS email_threads",
    "DROP TABLE IF EXISTS provider_accounts",
    "DROP TABLE IF EXISTS user_accounts",
)


def upgrade() -> None:
    connection = op.get_bind()
    for drop_table_statement in _RETIRED_TABLE_DROP_STATEMENTS:
        connection.execute(text(drop_table_statement))


def downgrade() -> None:
    # Intentionally a no-op: no earlier revision created these tables,
    # so downgrading past this revision must not resurrect them.
    pass
