"""Merge the NewsDOM provider branch into the unified migration graph.

Revision ID: 0015_merge_newsdom_email_heads
Revises: 0010_newsdom_providers, 0014_merge_email_read_state
Create Date: 2026-07-13 00:00:00.000000

The NewsDOM provider migration and the email read-state merge both descend
from the project graph revision through separate branches. This pure graph
merge restores a single Alembic head without applying additional DDL.
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0015_merge_newsdom_email_heads"
down_revision = ("0010_newsdom_providers", "0014_merge_email_read_state")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Unify the parent revisions without changing the database schema."""


def downgrade() -> None:
    """Leave the parent branch schemas intact when removing the merge node."""
