"""Merge the 0011_email_read_state branch back onto the mainline.

Two migration heads existed on ``develop``:

* the mainline
  ``0009_project_graph_projection -> 0010_language_agnostic_search ->
  0011_email_model_reconciliation -> 0012_llm_batch_orchestrator ->
  0013_scopeweave_promotion``, and
* a parallel ``0009_project_graph_projection -> 0011_email_read_state`` branch
  (the ``email_records.is_read`` read-state column) that was never chained onto
  the mainline.

``alembic upgrade head`` — the managed migration path run by
``scripts/migrate_db.py`` — fails with "Multiple head revisions are present for
given argument 'head'" whenever the graph has more than one head, so deployments
that apply migrations to ``head`` were broken. This revision is a pure graph
merge that reconciles both heads into a single head. It performs no schema
change: each parent branch already applied its own DDL, and running both
branches then this merge leaves the schema exactly as the union of the two.
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0014_merge_email_read_state"
down_revision = ("0011_email_read_state", "0013_scopeweave_promotion")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: a merge revision only unifies the migration graph. Both parent
    # branches already applied their schema changes, so there is nothing to do.
    pass


def downgrade() -> None:
    # No-op: this revision adds no schema; splitting the graph back into two
    # heads is intentionally unsupported, so there is nothing to reverse.
    pass
