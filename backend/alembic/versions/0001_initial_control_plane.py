"""initial control plane schema

Revision ID: 0001_initial_control_plane
Revises:
Create Date: 2026-06-15 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect, text

from db.models import Base
from scripts.bootstrap_db import schema_backfill_sql

revision = "0001_initial_control_plane"
down_revision = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(connection)
    legacy_emails_present = inspect(connection).has_table("emails")
    for statement in schema_backfill_sql():
        # The retired `emails` table existed only in legacy schemas. Fresh
        # databases are created from current ORM metadata (`email_records`), so
        # its compatibility-only index must not make revision 0001 depend on a
        # table that is intentionally absent.
        if not legacy_emails_present and "ix_emails_owner_date" in str(statement):
            continue
        connection.execute(statement)


def downgrade() -> None:
    # Baseline migration: production rollbacks should restore from backup or a
    # later explicit down revision rather than dropping customer-owned metadata.
    return None
