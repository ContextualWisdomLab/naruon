"""Replace whole-document GiST leaf arrays with full-content GIN indexes.

Keep migration 0010 immutable and preserve its normalization and index names.
GIN supports trigram predicates, not distance-only kNN acceleration; unchanged
ranking queries require measured performance evidence before this proposal lands.
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_search_trigram_storage"
down_revision = "0019_email_read_state_repair"

_SEARCH_INDEX_DEFINITIONS = (
    (
        "ix_email_records_search_document_trgm",
        "email_records",
        "search_normalized_text(coalesce(subject, '') || ' ' || body)",
    ),
    (
        "ix_email_attachments_content_trgm",
        "email_attachments",
        "search_normalized_text(content)",
    ),
    (
        "ix_content_segments_safe_text_trgm",
        "content_segments",
        "search_normalized_text(safe_text_content)",
    ),
    (
        "ix_project_graph_objects_search_document_trgm",
        "project_graph_objects",
        "search_normalized_text(title || ' ' || summary)",
    ),
)


def upgrade() -> None:
    """Rebuild the four owner indexes atomically without rewriting documents."""
    for index_name, table_name, document_expression in _SEARCH_INDEX_DEFINITIONS:
        op.drop_index(index_name, table_name=table_name, if_exists=True)
        op.create_index(
            index_name,
            table_name,
            [sa.literal_column(document_expression).label("search_document")],
            postgresql_using="gin",
            postgresql_ops={"search_document": "gin_trgm_ops"},
        )


def downgrade() -> None:
    """Keep corrected indexes so application rollback preserves large records."""
    # Reinstating GiST can fail once valid high-entropy documents are stored.
    # A different index strategy needs its own forward, data-preserving repair.
    return None
