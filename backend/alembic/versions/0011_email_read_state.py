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
    # A fresh install's 0001 migration creates only the current ORM tables
    # (email_records, which already carries is_read) via
    # Base.metadata.create_all(); the legacy "emails" table this migration
    # targets exists only on databases provisioned before that rename.
    if not sa.inspect(op.get_bind()).has_table("emails"):
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
    if not sa.inspect(op.get_bind()).has_table("emails"):
        return
    op.drop_column("emails", "is_read")
