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
    # No-op: this revision only reconciles a retired ``emails`` table. Dropping
    # ``is_read`` when the column is present would also remove a pre-existing
    # column this revision did not create.
    return
