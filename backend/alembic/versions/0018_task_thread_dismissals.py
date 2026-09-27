"""Preserve task provenance when a tentative timeline link is dismissed.

Revision ID: 0018_task_thread_dismissals
Revises: 0017_merge_newsdom_carddav_heads
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_task_thread_dismissals"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_TABLE = "ticket_task_thread_dismissals"


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("dismissal_id", sa.Integer(), primary_key=True),
            sa.Column("ticket_task_id", sa.Integer(), nullable=False),
            sa.Column("thread_key", sa.String(length=512), nullable=False),
            sa.Column("actor_user_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["ticket_task_id"], ["ticket_tasks.task_id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint(
                "ticket_task_id",
                "thread_key",
                name="uq_ticket_task_thread_dismissals_link",
            ),
        )


def downgrade() -> None:
    op.drop_table(_TABLE, if_exists=True)
