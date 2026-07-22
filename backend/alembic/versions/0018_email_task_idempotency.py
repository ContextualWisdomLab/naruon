"""Enforce idempotency for email-derived ticket tasks.

Revision ID: 0018_email_task_idempotency
Revises: 0017_merge_newsdom_carddav_heads
Create Date: 2026-07-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_email_task_idempotency"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_INDEX_NAME = "uq_ticket_tasks_email_item"


def upgrade() -> None:
    """Collapse prior exact replays before installing the unique boundary."""
    op.execute(
        sa.text(
            """
            DELETE FROM ticket_tasks AS duplicate
            USING ticket_tasks AS canonical
            WHERE duplicate.task_id > canonical.task_id
              AND duplicate.user_id = canonical.user_id
              AND COALESCE(duplicate.organization_id, '') =
                  COALESCE(canonical.organization_id, '')
              AND duplicate.source_type = 'email'
              AND canonical.source_type = 'email'
              AND duplicate.email_id IS NOT NULL
              AND duplicate.email_id = canonical.email_id
              AND duplicate.task_title = canonical.task_title
            """
        )
    )
    op.create_index(
        _INDEX_NAME,
        "ticket_tasks",
        [
            "user_id",
            sa.text("COALESCE(organization_id, '')"),
            "source_type",
            "email_id",
            sa.text("sha256(convert_to(task_title, 'UTF8'))"),
        ],
        unique=True,
        postgresql_where=sa.text("source_type = 'email' AND email_id IS NOT NULL"),
        if_not_exists=True,
    )


def downgrade() -> None:
    """Remove the uniqueness boundary; collapsed replay rows stay collapsed."""
    op.drop_index(
        _INDEX_NAME,
        table_name="ticket_tasks",
        if_exists=True,
    )
