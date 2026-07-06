"""add search fts and vector indexes

Revision ID: 0010_search_fts_vector_indexes
Revises: 0009_project_graph_projection
Create Date: 2026-07-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from db.search_indexes import search_index_statements

revision = "0010_search_fts_vector_indexes"
down_revision = "0009_project_graph_projection"


def _pgvector_version(connection) -> str | None:
    return connection.execute(
        sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar()


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    statements = search_index_statements(_pgvector_version(connection))
    # CONCURRENTLY cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        for _index_name, statement in statements:
            op.execute(sa.text(statement))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    statements = search_index_statements(_pgvector_version(connection))
    with op.get_context().autocommit_block():
        for index_name, _statement in statements:
            op.execute(
                sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
            )
