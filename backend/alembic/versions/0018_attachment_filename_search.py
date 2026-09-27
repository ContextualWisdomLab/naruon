"""Index attachment filenames with content for lexical search.

Revision ID: 0018_attachment_filename_search
Revises: 0017_merge_newsdom_carddav_heads
"""

from alembic import op
from sqlalchemy import text

revision = "0018_attachment_filename_search"
down_revision = "0017_merge_newsdom_carddav_heads"
branch_labels = None
depends_on = None

_DROP_INDEX_SQL = "DROP INDEX IF EXISTS ix_email_attachments_content_trgm"
_CREATE_INDEX_SQL = (
    "CREATE INDEX ix_email_attachments_content_trgm "
    "ON email_attachments USING gist "
    "((search_normalized_text(coalesce(filename, '') || ' ' || "
    "coalesce(content, ''))) gist_trgm_ops(siglen=256))"
)
_RESTORE_INDEX_SQL = (
    "CREATE INDEX ix_email_attachments_content_trgm "
    "ON email_attachments USING gist "
    "((search_normalized_text(content)) gist_trgm_ops(siglen=256))"
)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(text(_DROP_INDEX_SQL))
    connection.execute(text(_CREATE_INDEX_SQL))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(text(_DROP_INDEX_SQL))
    connection.execute(text(_RESTORE_INDEX_SQL))
