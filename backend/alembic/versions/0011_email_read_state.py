"""Add is_read to emails (IMAP \\Seen read state).

Existing rows default to read so historical/file imports do not surface as unread.
"""

from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_email_read_state"
down_revision = "0009_project_graph_projection"
branch_labels = None
depends_on = None


def _legacy_emails_table_present() -> bool:
    # Offline SQL generation (``alembic upgrade --sql``) has no live
    # connection to introspect -- ``op.get_bind()`` returns a MockConnection
    # that ``sa.inspect`` rejects outright. There is no target database to
    # ask "does this legacy table exist" at generation time either, so this
    # migration is a no-op for offline output; a DBA applying it against a
    # database that still carries the legacy ``emails`` table runs it online
    # instead, where introspection works.
    if context.is_offline_mode():
        return False
    return "emails" in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Fresh installations materialize the current ``email_records`` model in
    # the 0001 baseline, including ``is_read``.  This historical side branch
    # only applies to databases that still carry its legacy ``emails`` table.
    if not _legacy_emails_table_present():
        return
    op.add_column(
        "emails",
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    if not _legacy_emails_table_present():
        return
    op.drop_column("emails", "is_read")
