"""Add is_read to emails (IMAP \\Seen read state).

Existing rows default to read so historical/file imports do not surface as unread.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_email_read_state"
down_revision = "0009_project_graph_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``emails`` was the pre-reconciliation email table. ``email_records`` is now
    # the single source of truth and already declares ``is_read`` via the model
    # metadata created in 0001, so this legacy column add only applies to older
    # databases that still carry the retired ``emails`` table. Guard on the table
    # existing (matching the has_table/has_column pattern used by later
    # revisions) so ``alembic upgrade head`` succeeds on fresh databases.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("emails"):
        return
    existing_columns = {column["name"] for column in inspector.get_columns("emails")}
    if "is_read" in existing_columns:
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
    # Intentionally a no-op. The upgrade only ever adds ``emails.is_read`` to a
    # legacy database that still carries the retired ``emails`` table, and it
    # skips the add when the column already exists. Because that makes the
    # upgrade conditional, downgrade cannot tell whether this revision created
    # the column or whether it predated the revision, so dropping it here would
    # risk destroying data the revision never owned. Rolling back past this
    # revision therefore leaves the column in place.
    return None
