"""Canonical DDL for the search FTS/vector indexes.

Single source of truth shared by the Alembic migration and the Postgres
integration tests, so what tests verify is exactly what production creates.

The vector index uses HNSW when the installed pgvector supports it
(>= 0.5.0), otherwise IVFFlat. CONCURRENTLY keeps large index builds from
locking writes; callers must run these outside a transaction.
"""

_HNSW_MIN_VERSION = (0, 5, 0)


def _parse_version(version: str | None) -> tuple[int, ...]:
    if not version:
        return (0,)
    parts = []
    for token in version.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def vector_index_method(pgvector_version: str | None) -> str:
    if _parse_version(pgvector_version) >= _HNSW_MIN_VERSION:
        return "hnsw"
    return "ivfflat"


def search_index_statements(
    pgvector_version: str | None,
    *,
    concurrently: bool = True,
) -> list[tuple[str, str]]:
    """(index_name, CREATE INDEX sql) pairs for the search read path."""
    method = vector_index_method(pgvector_version)
    with_clause = "" if method == "hnsw" else " WITH (lists = 100)"
    conc = "CONCURRENTLY " if concurrently else ""
    return [
        (
            "ix_email_records_body_fts",
            f"CREATE INDEX {conc}IF NOT EXISTS ix_email_records_body_fts "
            "ON email_records USING gin (to_tsvector('english', body))",
        ),
        (
            "ix_email_records_embedding_vec",
            f"CREATE INDEX {conc}IF NOT EXISTS ix_email_records_embedding_vec "
            f"ON email_records USING {method} (embedding vector_cosine_ops)"
            f"{with_clause}",
        ),
        (
            "ix_email_attachments_content_fts",
            f"CREATE INDEX {conc}IF NOT EXISTS ix_email_attachments_content_fts "
            "ON email_attachments USING gin (to_tsvector('english', content))",
        ),
        (
            "ix_email_attachments_embedding_vec",
            f"CREATE INDEX {conc}IF NOT EXISTS ix_email_attachments_embedding_vec "
            f"ON email_attachments USING {method} (embedding vector_cosine_ops)"
            f"{with_clause}",
        ),
    ]
