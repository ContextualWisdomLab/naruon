"""Merge the immutable read-state follow-up into the migration graph.

Revision ID: 0019_merge_email_read_state_ownership
Revises: 0017_merge_newsdom_carddav_heads, 0018_email_read_state_ownership
Create Date: 2026-08-12 00:00:00.000000
"""

from __future__ import annotations

revision = "0019_merge_email_read_state_ownership"
down_revision = ("0017_merge_newsdom_carddav_heads", "0018_email_read_state_ownership")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Unify the existing application branches without additional DDL."""


def downgrade() -> None:
    """Keep the parent branch schemas intact when removing the merge node."""
