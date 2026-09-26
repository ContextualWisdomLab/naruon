"""Exercise owner-private calendar source migration against PostgreSQL."""

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings
from db.models import Base


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_calendar_source_revision_upgrades_and_downgrades():
    schema = f"e1_calendar_source_migration_{uuid.uuid4().hex[:12]}"
    root_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    revision_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0022_calendar_source_documents.py"
    )
    spec = importlib.util.spec_from_file_location(
        "calendar_source_revision", revision_path
    )
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)
            await connection.execute(
                text("ALTER TABLE source_events DROP COLUMN calendar_document_id")
            )
            await connection.execute(text("DROP TABLE calendar_source_documents"))

            def verify_revision(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    revision.upgrade()
                inspector = inspect(sync_connection)
                assert inspector.has_table("calendar_source_documents")
                assert {
                    column["name"]
                    for column in inspector.get_columns("calendar_source_documents")
                } == {
                    column.name
                    for column in Base.metadata.tables[
                        "calendar_source_documents"
                    ].columns
                }
                assert "calendar_document_id" in {
                    column["name"] for column in inspector.get_columns("source_events")
                }
                assert any(
                    fk["constrained_columns"] == ["calendar_document_id"]
                    and fk["referred_table"] == "calendar_source_documents"
                    for fk in inspector.get_foreign_keys("source_events")
                )
                with Operations.context(MigrationContext.configure(sync_connection)):
                    revision.downgrade()
                inspector.clear_cache()
                assert not inspector.has_table("calendar_source_documents")
                assert "calendar_document_id" not in {
                    column["name"] for column in inspector.get_columns("source_events")
                }

            await connection.run_sync(verify_revision)
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
