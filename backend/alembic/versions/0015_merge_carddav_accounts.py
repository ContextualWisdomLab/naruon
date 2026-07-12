"""Merge the CardDAV accounts branch back onto the mainline.

The live-test accounts branch adds ``0010_carddav_accounts`` from
``0009_project_graph_projection`` while develop already advanced through
``0014_merge_email_read_state``. Without a merge revision, Alembic sees both as
heads and ``alembic upgrade head`` is ambiguous.

This revision has no schema operations. The parent branches already apply their
own DDL; this file only records the graph reconciliation.
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0015_merge_carddav_accounts"
down_revision = ("0010_carddav_accounts", "0014_merge_email_read_state")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: this merge revision only unifies the Alembic heads."""


def downgrade() -> None:
    """No-op: a graph merge adds no schema to reverse."""
