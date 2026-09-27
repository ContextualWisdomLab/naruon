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
    end_index_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0023_event_page_indexes.py"
    )
    end_index_spec = importlib.util.spec_from_file_location(
        "source_event_end_index_revision", end_index_path
    )
    assert end_index_spec is not None and end_index_spec.loader is not None
    end_index_revision = importlib.util.module_from_spec(end_index_spec)
    end_index_spec.loader.exec_module(end_index_revision)
    dependency_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0024_event_dependencies.py"
    )
    dependency_spec = importlib.util.spec_from_file_location(
        "event_dependency_revision", dependency_path
    )
    assert dependency_spec is not None and dependency_spec.loader is not None
    dependency_revision = importlib.util.module_from_spec(dependency_spec)
    dependency_spec.loader.exec_module(dependency_revision)
    try:
        async with root_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)
            await connection.execute(
                text("ALTER TABLE source_events DROP COLUMN calendar_document_id")
            )
            await connection.execute(text("DROP TABLE calendar_source_documents"))
            await connection.execute(text("DROP INDEX ix_source_events_scope_end"))
            await connection.execute(text("DROP INDEX ix_source_events_scope_uid"))
            await connection.execute(text("DROP INDEX ix_event_relations_scope_uid"))
            await connection.execute(text("DROP INDEX ix_source_events_scope_key"))
            await connection.execute(
                text("ALTER TABLE source_events DROP COLUMN dependency_evidence")
            )
            await connection.execute(
                text(
                    "ALTER TABLE event_relations DROP CONSTRAINT ck_event_relations_enabler"
                )
            )
            await connection.execute(
                text("ALTER TABLE event_relations DROP COLUMN enabler_event_uid")
            )
            await connection.execute(
                text(
                    "ALTER TABLE event_relation_corrections DROP COLUMN before_enabler_event_uid"
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE event_relation_corrections DROP COLUMN after_enabler_event_uid"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX ix_event_relations_scope ON event_relations "
                    "(user_id, organization_id, workspace_id, visibility_scope)"
                )
            )

            def verify_revision(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    revision.upgrade()
                    end_index_revision.upgrade()
                    dependency_revision.upgrade()
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
                assert "ix_source_events_scope_end" in {
                    index["name"] for index in inspector.get_indexes("source_events")
                }
                assert "ix_source_events_scope_uid" in {
                    index["name"] for index in inspector.get_indexes("source_events")
                }
                assert "ix_event_relations_scope_uid" in {
                    index["name"] for index in inspector.get_indexes("event_relations")
                }
                assert "ix_source_events_scope_key" in {
                    index["name"] for index in inspector.get_indexes("source_events")
                }
                assert "dependency_evidence" in {
                    column["name"] for column in inspector.get_columns("source_events")
                }
                assert "enabler_event_uid" in {
                    column["name"]
                    for column in inspector.get_columns("event_relations")
                }
                with Operations.context(MigrationContext.configure(sync_connection)):
                    dependency_revision.downgrade()
                    end_index_revision.downgrade()
                    revision.downgrade()
                inspector.clear_cache()
                assert not inspector.has_table("calendar_source_documents")
                assert "calendar_document_id" not in {
                    column["name"] for column in inspector.get_columns("source_events")
                }
                assert "ix_source_events_scope_end" not in {
                    index["name"] for index in inspector.get_indexes("source_events")
                }
                assert "ix_source_events_scope_uid" not in {
                    index["name"] for index in inspector.get_indexes("source_events")
                }
                assert "ix_event_relations_scope" in {
                    index["name"] for index in inspector.get_indexes("event_relations")
                }
                assert "dependency_evidence" not in {
                    column["name"] for column in inspector.get_columns("source_events")
                }

            await connection.run_sync(verify_revision)
    finally:
        await scoped_engine.dispose()
        async with root_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await root_engine.dispose()
