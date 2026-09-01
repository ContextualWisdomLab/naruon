"""Add is_read to emails (IMAP \\Seen read state).

Existing rows default to read so historical/file imports do not surface as unread.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_email_read_state"
down_revision = "0009_project_graph_projection"
branch_labels = None
depends_on = None

# Fresh installations materialize the current ``email_records`` model in the
# 0001 baseline, including ``is_read``. This historical side branch only
# applies to databases that still carry its legacy ``emails`` table.
#
# The condition has to be evaluated in SQL, not Python: offline SQL
# generation (``alembic upgrade --sql``, a real flag ``scripts/migrate_db.py``
# exposes) has no live connection to introspect with and no specific target
# database to ask "does this legacy table exist" at generation time either --
# the same static script is meant to later be applied by a DBA against
# whichever database they choose, fresh-install or legacy. A Python-side
# check (``sa.inspect(op.get_bind())``) can only ever answer that question
# for one hypothetical target chosen at generation time, so it is wrong for
# the other: skip unconditionally and the column silently never gets added
# for a legacy database that applies the generated script (while
# ``alembic_version`` still advances, permanently hiding the gap); inspect
# online and bake in one fixed answer and the same script fails outright
# against the other kind of target. A ``DO $$ ... $$`` block defers the
# check to apply time instead, so the one generated script is correct
# against either kind of target, online or offline-then-applied-later alike.
_UPGRADE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'emails'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'emails' AND column_name = 'is_read'
    ) THEN
        ALTER TABLE emails ADD COLUMN is_read boolean NOT NULL DEFAULT true;
    END IF;
END $$;
"""

_DOWNGRADE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'emails'
    ) THEN
        ALTER TABLE emails DROP COLUMN IF EXISTS is_read;
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(_UPGRADE_SQL)


def downgrade() -> None:
    op.execute(_DOWNGRADE_SQL)
