"""Exercise the event-relation Alembic step against isolated PostgreSQL DDL."""

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
async def test_event_relation_revision_upgrades_and_downgrades():
    schema = f"e1_relation_migration_{uuid.uuid4().hex[:12]}"
    root_engine = create_async_engine(settings.DATABASE_URL)
    scoped_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    revision_path = (
        Path(__file__).resolve().parents[1] / "alembic/versions/0021_event_relations.py"
    )
    spec = importlib.util.spec_from_file_location(
        "event_relation_revision", revision_path
    )
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)
            await connection.execute(text("DROP TABLE event_relation_corrections"))
            await connection.execute(text("DROP TABLE event_relations"))

            def verify_revision(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    revision.upgrade()
                inspector = inspect(sync_connection)
                assert inspector.has_table("event_relations")
                assert inspector.has_table("event_relation_corrections")
                assert {
                    column["name"]
                    for column in inspector.get_columns("event_relations")
                } == {
                    column.name
                    for column in Base.metadata.tables["event_relations"].columns
                } - {"enabler_event_uid"}
                with Operations.context(MigrationContext.configure(sync_connection)):
                    revision.downgrade()
                inspector.clear_cache()
                assert not inspector.has_table("event_relations")
                assert not inspector.has_table("event_relation_corrections")

            await connection.run_sync(verify_revision)
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
