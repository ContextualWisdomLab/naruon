"""Merge the NewsDOM document and CardDAV account migration heads.

Revision ID: 0017_merge_newsdom_carddav_heads
Revises: 0016_document_org_scope, 0015_merge_carddav_accounts
Create Date: 2026-07-13 00:00:00.000000

The NewsDOM branch adds organization scope to workspace documents while the
live-test accounts branch independently merges CardDAV accounts. Both parent
revisions already own their DDL, so this revision only reconciles the graph.
"""

from __future__ import annotations

revision = "0017_merge_newsdom_carddav_heads"
down_revision = ("0016_document_org_scope", "0015_merge_carddav_accounts")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Unify the parent revisions without changing the database schema."""


def downgrade() -> None:
    """Leave both parent branch schemas intact when removing the merge node."""
