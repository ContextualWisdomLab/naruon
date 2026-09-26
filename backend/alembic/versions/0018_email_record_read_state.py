"""Keep email read state available to SQL writers on existing databases."""

from alembic import op
import sqlalchemy as sa

revision = "0018_email_record_read_state"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("email_records"):
        return
    columns = {
        column["name"]: column for column in inspector.get_columns("email_records")
    }
    if "is_read" not in columns:
        op.add_column(
            "email_records",
            sa.Column(
                "is_read", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
        )
        return
    nullable = columns["is_read"]["nullable"]
    if nullable:
        op.execute("UPDATE email_records SET is_read = true WHERE is_read IS NULL")
    op.alter_column(
        "email_records",
        "is_read",
        existing_type=sa.Boolean(),
        nullable=False if nullable else None,
        server_default=sa.text("true"),
    )


def downgrade() -> None:
    # The default may predate this revision; keep it and all read-state data.
    return
