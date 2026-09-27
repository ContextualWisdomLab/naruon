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


def upgrade() -> None:
    op.drop_index(
        "ix_email_attachments_content_trgm",
        table_name="email_attachments",
        if_exists=True,
    )
    op.create_index(
        "ix_email_attachments_content_trgm",
        "email_attachments",
        [
            text(
                "(search_normalized_text(coalesce(filename, '') || ' ' || coalesce(content, ''))) gist_trgm_ops(siglen=256)"
            )
        ],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_attachments_content_trgm",
        table_name="email_attachments",
        if_exists=True,
    )
    op.create_index(
        "ix_email_attachments_content_trgm",
        "email_attachments",
        [text("(search_normalized_text(content)) gist_trgm_ops(siglen=256)")],
        postgresql_using="gist",
    )
