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
async def test_fresh_migration_chain_creates_attachment_fact_column(monkeypatch):
    from pathlib import Path
    import uuid

    from alembic.config import Config
    import asyncio

    from alembic import command
    from alembic.script import ScriptDirectory
    from alembic.runtime.environment import EnvironmentContext
    from sqlalchemy import inspect, text
    import sqlalchemy.ext.asyncio as async_sqlalchemy
    from sqlalchemy.ext.asyncio import create_async_engine

    from core.config import settings

    schema = f"attachment_migrations_{uuid.uuid4().hex}"
    engine = create_async_engine(settings.DATABASE_URL)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    script = ScriptDirectory.from_config(config)
    original_factory = async_sqlalchemy.async_engine_from_config

    def scoped_engine_factory(*args, **kwargs):
        kwargs["connect_args"] = {
            "server_settings": {"search_path": f"{schema},public"}
        }
        kwargs["execution_options"] = {"schema_translate_map": {None: schema}}
        return original_factory(*args, **kwargs)

    monkeypatch.setattr(
        async_sqlalchemy, "async_engine_from_config", scoped_engine_factory
    )
    original_configure = EnvironmentContext.configure

    def scoped_version_table(environment, *args, **kwargs):
        kwargs["version_table_schema"] = schema
        return original_configure(environment, *args, **kwargs)

    monkeypatch.setattr(EnvironmentContext, "configure", scoped_version_table)
    schema_created = False
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            schema_created = True
        await asyncio.to_thread(command.upgrade, config, "head")
        async with engine.begin() as connection:
            installed_heads = (
                (
                    await connection.execute(
                        text(f"SELECT version_num FROM {schema}.alembic_version")
                    )
                )
                .scalars()
                .all()
            )
            assert installed_heads == script.get_heads()

            def verify(sync_connection):
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

            await connection.run_sync(verify)
    finally:
        if schema_created:
            async with engine.begin() as connection:
                await connection.execute(
                    text(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_registry_sdk_and_api_preserve_late_window_quote(
    isolated_fact_sessionmaker, monkeypatch
):
    import hashlib
    import json

    import httpx
    from api.auth import AuthContext
    from api.emails import get_attachment_facts
    import services.project_graph.llm_extractor as extractor

    maker = isolated_fact_sessionmaker
    quote = "Acme will deliver."
    original_text = "x" * 2400 + quote + "y" * 2000
    async with maker() as session:
        segment = await _seed_source_segment(
            session, user_id="wire-user", organization_id="wire-org"
        )
        attachment = Attachment(
            email_id=segment.email_id, filename="terms.txt", content=original_text
        )
        session.add(attachment)
        await session.flush()
        segment.attachment_id = attachment.id
        segment.source_kind = "attachment"
        segment.source_record_uid = f"attachment:{attachment.id}"
        segment.safe_text_content = original_text
        await session.commit()
        attachment_id, email_id, segment_uid = (
            attachment.id,
            segment.email_id,
            segment.content_segment_uid,
        )

    monkeypatch.setattr(worker, "AsyncSessionLocal", maker)
    monkeypatch.setattr(worker.settings, "PROJECT_GRAPH_EXTRACTOR", "llm")
    monkeypatch.setattr(
        worker,
        "resolve_runtime_llm_provider",
        AsyncMock(
            return_value=SimpleNamespace(
                api_key="synthetic",
                base_url="https://synthetic.invalid/v1",
                chat_model="synthetic-model",
            )
        ),
    )
    requests, clients = [], []

    def response(request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        entries = json.loads(
            body["messages"][1]["content"].removeprefix("SEGMENTS_JSON: ")
        )["segments"]
        requests.append(entries)
        objects = [
            {
                "object_type": "attachment_fact",
                "title": "Delivery",
                "summary": quote,
                "source_segment_uids": [entry["content_segment_uid"]],
                "confidence": 0.8,
                "fact_kind": "commitment",
                "fact_value": "will deliver",
                "evidence_excerpt": quote,
            }
            for entry in entries
            if quote in entry["text"]
        ]
        return httpx.Response(
            200,
            json={
                "id": "synthetic-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "synthetic-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {"objects": objects, "relations": []}
                            ),
                        },
                    }
                ],
            },
        )

    async def transport(base_url):
        client = httpx.AsyncClient(transport=httpx.MockTransport(response))
        clients.append(client)
        return base_url, client

    monkeypatch.setattr(extractor, "build_llm_provider_http_client", transport)
    assert await worker.infer_attachment_facts(attachment_id) is True
    assert len(requests) > 1
    assert all(client.is_closed for client in clients)
    assert all(len(entry["text"]) <= 2000 for entries in requests for entry in entries)
    async with maker() as session:
        fact = await session.scalar(select(ProjectGraphObjectRecord))
        assert (
            fact.attributes_json["source_segment_hash"]
            == hashlib.sha256(original_text.encode()).hexdigest()
        )
        page = await get_attachment_facts(
            email_id,
            limit=100,
            offset=0,
            db=session,
            auth_context=AuthContext(
                user_id="wire-user",
                organization_id="wire-org",
                role="member",
                group_ids=(),
                workspace_id="workspace-wire-org",
            ),
        )
        assert len(page.facts) == 1
        assert page.facts[0].evidence_excerpt == quote
        assert page.facts[0].source_segment_uid == segment_uid
        assert page.facts[0].validation_status == "inferred_unverified"
