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


def _email_table() -> str:
    inspector = sa.inspect(op.get_bind())
    return "email_records" if inspector.has_table("email_records") else "emails"


def upgrade() -> None:
    table = _email_table()
    if any(
        column["name"] == "is_read"
        for column in sa.inspect(op.get_bind()).get_columns(table)
    ):
        return
    op.add_column(
        table,
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column(_email_table(), "is_read")
