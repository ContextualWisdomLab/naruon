"""Postgres-backed proof that the hybrid search arms are index-eligible.

Requires a reachable pgvector PostgreSQL at DATABASE_URL (pytest -m postgres).
Creates the schema plus the exact indexes migration 0010 creates (shared DDL
in db.search_indexes), then EXPLAIN-asserts each arm's plan uses its index.
``enable_seqscan = off`` pins the planner so the assertion is about index
*eligibility*, independent of table size.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from db.search_indexes import search_index_statements

pytestmark = pytest.mark.postgres

_LEXICAL_ARM_SQL = (
    # Mirrors build_lexical_email_stmt: @@-gated, ranked, limited.
    "SELECT id FROM email_records "
    "WHERE to_tsvector('english', body) @@ plainto_tsquery('english', 'meeting') "
    "ORDER BY ts_rank_cd(to_tsvector('english', body), "
    "plainto_tsquery('english', 'meeting')) DESC LIMIT 20"
)
_VECTOR_ARM_SQL = (
    # Mirrors build_vector_email_stmt: pure distance ORDER BY + LIMIT.
    "SELECT id FROM email_records "
    "ORDER BY embedding <=> '[0.1,0.2,0.3]'::vector LIMIT 20"
)


@pytest.mark.asyncio
async def test_search_arm_queries_use_migration_0010_indexes():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS email_records ("
                    "id serial PRIMARY KEY, body text, embedding vector(3))"
                )
            )
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS email_attachments ("
                    "id serial PRIMARY KEY, content text, embedding vector(3))"
                )
            )
            version = await conn.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            # The exact DDL migration 0010 runs (non-concurrent inside a test).
            for _name, statement in search_index_statements(
                version, concurrently=False
            ):
                await conn.execute(text(statement))
            await conn.execute(text("ANALYZE email_records"))
            await conn.commit()

        async with engine.connect() as conn:
            await conn.execute(text("SET enable_seqscan = off"))

            lexical_plan = "\n".join(
                row[0]
                for row in await conn.execute(
                    text("EXPLAIN (COSTS OFF) " + _LEXICAL_ARM_SQL)
                )
            )
            assert "ix_email_records_body_fts" in lexical_plan

            vector_plan = "\n".join(
                row[0]
                for row in await conn.execute(
                    text("EXPLAIN (COSTS OFF) " + _VECTOR_ARM_SQL)
                )
            )
            assert "ix_email_records_embedding_vec" in vector_plan
    finally:
        await engine.dispose()
