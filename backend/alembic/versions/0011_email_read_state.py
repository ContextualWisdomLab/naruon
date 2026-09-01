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
    # Fresh installations materialize the current ``email_records`` model in
    # the 0001 baseline, including ``is_read``.  This historical side branch
    # only applies to databases that still carry its legacy ``emails`` table.
    if "emails" not in sa.inspect(op.get_bind()).get_table_names():
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
    if "emails" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_column("emails", "is_read")
