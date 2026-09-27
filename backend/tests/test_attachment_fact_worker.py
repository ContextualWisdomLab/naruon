from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

import services.attachment_fact_worker as worker
from db.models import Attachment, ProjectGraphObjectRecord
from services.project_graph.llm_extractor import (
    ExtractedObjectPayload,
    ExtractionPayload,
    _validated_objects,
    LLM_EXTRACTOR_NAME,
    LLM_EXTRACTOR_VERSION,
)
from services.project_graph.models import ProjectSemanticExtractionResult
from tests.test_project_graph_projection import (
    isolated_fact_sessionmaker as _shared_fact_sessions,
    _seed_source_segment,
)


isolated_fact_sessionmaker = _shared_fact_sessions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome", ["fact", "empty", "changed", "fallback", "owner", "missing"]
)
async def test_inference_closes_read_session_and_rechecks_source(
    isolated_fact_sessionmaker,
    monkeypatch,
    outcome,
):
    maker = isolated_fact_sessionmaker
    async with maker() as session:
        segment = await _seed_source_segment(
            session, user_id="worker-user", organization_id="worker-org"
        )
        attachment = Attachment(
            email_id=segment.email_id,
            filename="terms.txt",
            content="Acme will deliver.",
        )
        session.add(attachment)
        await session.flush()
        segment.attachment_id = attachment.id
        segment.source_kind = "attachment"
        segment.safe_text_content = attachment.content
        await session.commit()
        attachment_id = attachment.id
        segment_id = segment.content_segment_id
    states = []

    @asynccontextmanager
    async def sessions():
        slot = len(states)
        states.append("open")
        async with maker() as session:
            yield session
        states[slot] = "closed"

    monkeypatch.setattr(worker, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(
        worker,
        "resolve_runtime_llm_provider",
        AsyncMock(
            return_value=None
            if outcome == "missing"
            else SimpleNamespace(api_key="test", base_url=None, chat_model="test")
        ),
    )

    async def extract(segments, **_kwargs):
        assert states[-1] == "closed" and "open" not in states
        if outcome == "changed":
            from db.models import ContentSegmentRecord

            async with maker() as session:
                source = await session.get(ContentSegmentRecord, segment_id)
                source.safe_text_content = "Changed source"
                await session.commit()
        if outcome == "owner":
            from db.models import Email

            async with maker() as session:
                email = await session.get(Email, segment.email_id)
                email.user_id = "changed-owner"
                await session.commit()
        candidates = _validated_objects(
            ExtractionPayload(
                objects=[
                    ExtractedObjectPayload(
                        object_type="attachment_fact",
                        title="Delivery",
                        summary="Acme will deliver.",
                        source_segment_uids=[segments[0].content_segment_uid],
                        confidence=0.8,
                        fact_kind="commitment",
                        fact_value="will deliver",
                        evidence_excerpt="Acme will deliver.",
                    )
                ]
            ),
            {s.content_segment_uid: s for s in segments},
        )
        return ProjectSemanticExtractionResult(
            objects=tuple(o for _, o in candidates) if outcome != "empty" else (),
            edges=(),
            extractor_name="keyword" if outcome == "fallback" else LLM_EXTRACTOR_NAME,
            extractor_version=LLM_EXTRACTOR_VERSION,
        )

    mocked_extract = AsyncMock(side_effect=extract)
    monkeypatch.setattr(worker, "run_extraction", mocked_extract)
    completed = await worker.infer_attachment_facts(attachment_id)
    assert completed == (outcome in {"fact", "empty"})
    async with maker() as session:
        attachment = await session.get(Attachment, attachment_id)
        assert attachment.fact_extractor_version == (
            LLM_EXTRACTOR_VERSION if completed else None
        )
        facts = (await session.scalars(select(ProjectGraphObjectRecord))).all()
        assert len(facts) == (1 if outcome == "fact" else 0)
    if completed:
        assert await worker.infer_attachment_facts(attachment_id) is False
        mocked_extract.assert_awaited_once()
    if outcome == "fact":
        async with maker() as session:
            saved = await session.scalar(select(ProjectGraphObjectRecord))
            saved.title = "User correction"
            attachment = await session.get(Attachment, attachment_id)
            attachment.fact_extractor_version = None
            await session.commit()
        assert await worker.infer_attachment_facts(attachment_id) is True
        async with maker() as session:
            saved = await session.scalar(select(ProjectGraphObjectRecord))
            assert saved.title == "User correction"


def test_completion_marker_migration_roundtrip():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/0019_attachment_fact_extractor_version.py"
    )
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(path.parents[1]))
    assert ScriptDirectory.from_config(config).get_heads() == [
        "0019_attachment_fact_version"
    ]

    spec = importlib.util.spec_from_file_location("fact_version_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with create_engine("sqlite://").begin() as connection:
        connection.execute(
            text("CREATE TABLE email_attachments (id INTEGER PRIMARY KEY)")
        )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()
        assert "fact_extractor_version" in {
            c["name"] for c in inspect(connection).get_columns("email_attachments")
        }
        module.downgrade()
        assert "fact_extractor_version" not in {
            c["name"] for c in inspect(connection).get_columns("email_attachments")
        }


@pytest.mark.asyncio
async def test_fresh_migration_chain_creates_attachment_fact_column():
    from pathlib import Path
    import uuid

    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine

    from core.config import settings

    schema = f"attachment_migrations_{uuid.uuid4().hex}"
    engine = create_async_engine(settings.DATABASE_URL)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    script = ScriptDirectory.from_config(config)
    schema_created = False
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            schema_created = True
        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL search_path TO {schema}, public"))

            def upgrade(sync_connection):
                sync_connection = sync_connection.execution_options(
                    schema_translate_map={None: schema}
                )
                with Operations.context(MigrationContext.configure(sync_connection)):
                    for revision in reversed(list(script.walk_revisions())):
                        revision.module.upgrade()
                columns = {
                    column["name"]
                    for column in inspect(sync_connection).get_columns(
                        "email_attachments", schema=schema
                    )
                }
                assert "fact_extractor_version" in columns
                assert inspect(sync_connection).has_table(
                    "email_records", schema=schema
                )

            await connection.run_sync(upgrade)
    finally:
        if schema_created:
            async with engine.begin() as connection:
                await connection.execute(
                    text(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                )
        await engine.dispose()
