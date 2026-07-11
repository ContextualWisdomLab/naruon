"""language-agnostic search surfaces (G6)

Replaces the language-dependent ``to_tsvector('english', ...)`` search
scaffolding with language-agnostic infrastructure:

- ``pg_trgm`` + ``unaccent`` extensions (both PostgreSQL-licensed
  contrib modules shipped with the pgvector/pgvector:pg16 image).
- ``search_normalized_text(text)``: an IMMUTABLE wrapper combining
  Unicode NFC normalization (UAX #15 — composes decomposed Vietnamese
  and Korean input), accent folding via ``unaccent`` with an explicit
  dictionary (the documented pattern for making unaccent indexable),
  and lowercasing. Query and document sides both go through it.
- GiST character-trigram expression indexes over the four search
  surfaces (email subject+body, attachment content, content segments,
  project-graph objects) serving ``<->>`` word-similarity kNN ordering.
  Character trigrams need no per-language tokenizer, so CJK/Vietnamese
  queries match without a morphological analyzer.

Revision ID: 0010_language_agnostic_search
Revises: 0009_project_graph_projection
Create Date: 2026-07-11 00:00:00.000000
"""

from alembic import op
from sqlalchemy import text

revision = "0010_language_agnostic_search"
down_revision = "0009_project_graph_projection"

# IMMUTABLE wrapper so the expression is indexable; the bare
# ``unaccent(text)`` form is only STABLE because it resolves its
# dictionary through the search path, hence the explicit
# ``regdictionary`` argument (see PostgreSQL docs, F.50 unaccent).
_NORMALIZE_FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION search_normalized_text(input_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT lower(
        public.unaccent(
            'public.unaccent'::regdictionary,
            normalize(coalesce(input_text, ''), NFC)
        )
    )
$$
"""

_TRIGRAM_INDEX_STATEMENTS = {
    "ix_email_records_search_document_trgm": (
        "CREATE INDEX IF NOT EXISTS ix_email_records_search_document_trgm "
        "ON email_records USING gist "
        "((search_normalized_text(coalesce(subject, '') || ' ' || body)) "
        "gist_trgm_ops(siglen=256))"
    ),
    "ix_email_attachments_content_trgm": (
        "CREATE INDEX IF NOT EXISTS ix_email_attachments_content_trgm "
        "ON email_attachments USING gist "
        "((search_normalized_text(content)) gist_trgm_ops(siglen=256))"
    ),
    "ix_content_segments_safe_text_trgm": (
        "CREATE INDEX IF NOT EXISTS ix_content_segments_safe_text_trgm "
        "ON content_segments USING gist "
        "((search_normalized_text(safe_text_content)) "
        "gist_trgm_ops(siglen=256))"
    ),
    "ix_project_graph_objects_search_document_trgm": (
        "CREATE INDEX IF NOT EXISTS "
        "ix_project_graph_objects_search_document_trgm "
        "ON project_graph_objects USING gist "
        "((search_normalized_text(title || ' ' || summary)) "
        "gist_trgm_ops(siglen=256))"
    ),
}

_TRIGRAM_INDEX_DROP_STATEMENTS = (
    "DROP INDEX IF EXISTS ix_email_records_search_document_trgm",
    "DROP INDEX IF EXISTS ix_email_attachments_content_trgm",
    "DROP INDEX IF EXISTS ix_content_segments_safe_text_trgm",
    "DROP INDEX IF EXISTS ix_project_graph_objects_search_document_trgm",
)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))

    connection.execute(text(_NORMALIZE_FUNCTION_DDL))

    for create_index_statement in _TRIGRAM_INDEX_STATEMENTS.values():
        connection.execute(text(create_index_statement))


def downgrade() -> None:
    connection = op.get_bind()
    for drop_index_statement in _TRIGRAM_INDEX_DROP_STATEMENTS:
        connection.execute(text(drop_index_statement))
    connection.execute(
        text("DROP FUNCTION IF EXISTS search_normalized_text(text)")
    )
    # Extensions stay installed: other objects may depend on them and
    # leaving contrib extensions in place is safe.
