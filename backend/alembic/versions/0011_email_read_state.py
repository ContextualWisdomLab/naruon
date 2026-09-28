"""Add is_read to existing mail tables (IMAP \\Seen read state).

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
    inspector = sa.inspect(op.get_bind())
    for table in ("email_records", "emails"):
        if inspector.has_table(table) and not any(
            column["name"] == "is_read" for column in inspector.get_columns(table)
        ):
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
    # The column may have predated this idempotent revision; do not erase it.
    pass
