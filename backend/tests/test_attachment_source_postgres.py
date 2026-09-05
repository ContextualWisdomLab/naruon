"""Real published PDF retention on a migrated database, without recognition claims."""

import asyncio
import base64
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from db.models import Attachment, Document, Email, Workspace
from services.attachment_parser import parse_email_attachment
import services.newsdom_client as newsdom_client_module
import services.newsdom_worker as newsdom_worker_module
from services.newsdom_pdf_recognition import NewsdomRuntimeConfig
from services.newsdom_worker import process_pending_attachment, process_pending_document
from tests.test_email_read_state_migration_postgres import (
    _run_migrations,
    fresh_database_url as fresh_database_url,
)

pytestmark = pytest.mark.postgres

NASA_PDF_URL = "https://www.nasa.gov/wp-content/uploads/2019/11/earth_at_night_508.pdf"
NASA_PDF_SIZE = 40_758_835
NASA_PDF_SHA256 = "8e622ca8f6d1ba0cf809549bddfee69e6754c3a3480d151c1fb54baf49b09be0"


@pytest.fixture(scope="session")
def published_pdf_bytes(pytestconfig):
    """Reuse a verified public-domain corpus; reject changed or oversized downloads."""
    cache_file = Path(pytestconfig.cache.makedir("attachment_source")) / "earth_at_night_508.pdf"
    if cache_file.exists():
        with cache_file.open("rb") as cache_stream:
            pdf_bytes = cache_stream.read(NASA_PDF_SIZE + 1)
    else:
        payload_buffer = bytearray()
        with httpx.stream(
            "GET", NASA_PDF_URL, headers={"Accept-Encoding": "identity"},
            follow_redirects=False, trust_env=False, timeout=60,
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].split(";", 1)[0] == "application/pdf"
            for response_chunk in response.iter_bytes(chunk_size=64 * 1024):
                assert len(payload_buffer) + len(response_chunk) <= NASA_PDF_SIZE
                payload_buffer.extend(response_chunk)
        pdf_bytes = bytes(payload_buffer)
    assert len(pdf_bytes) == NASA_PDF_SIZE
    assert hashlib.sha256(pdf_bytes).hexdigest() == NASA_PDF_SHA256
    if not cache_file.exists():
        cache_file.write_bytes(pdf_bytes)
    return pdf_bytes


@pytest.mark.parametrize("source_kind", ["attachment", "document"])
@pytest.mark.asyncio
async def test_published_pdf_survives_pending_rejection_and_transaction_rollback(
    fresh_database_url, published_pdf_bytes, source_kind, monkeypatch, caplog,
):
    """Catch discarded/truncated bytes and identity changes across committed sessions."""
    _run_migrations(fresh_database_url)
    engine = create_async_engine(fresh_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    parsed_source = parse_email_attachment(
        filename="earth_at_night_508.pdf", content_type="application/pdf",
        raw_content=published_pdf_bytes,
    )
    assert parsed_source.parse_status == "pdf_dom_recognition_pending"
    workspace = Workspace(workspace_id="workspace-pdf-retention", workspace_name="PDF retention")
    if source_kind == "attachment":
        email = Email(
            user_id="pdf-retention-user", organization_id="pdf-retention-org",
            message_id="pdf-retention-source", sender="NASA", subject="Earth at Night",
            body="Earth at Night", date=datetime(2019, 12, 9, tzinfo=timezone.utc),
        )
        source_record = Attachment(
            email=email, filename=parsed_source.filename, content=parsed_source.content,
            content_type=parsed_source.content_type, parse_status=parsed_source.parse_status,
            parser_key=parsed_source.parser_key, parse_content_type=parsed_source.parse_content_type,
        )
        source_key = Attachment.id
        content_field, status_field = "content", "parse_status"
        processor, argument_name = process_pending_attachment, "attachment"
    else:
        source_record = Document(
            workspace_entity=workspace, organization_id="pdf-retention-org",
            document_name=parsed_source.filename, document_type="pdf",
            document_content=parsed_source.content, document_status=parsed_source.parse_status,
        )
        source_key = Document.document_id
        content_field, status_field = "document_content", "document_status"
        processor, argument_name = process_pending_document, "document"

    async def no_provider(_session, _organization_id):
        """Exercise the real worker's unavailable-provider branch."""
        return None

    async def configured_provider(_session, _organization_id):
        """Select a provider; its real client must reject before network validation."""
        return NewsdomRuntimeConfig(
            base_url="https://newsdom.example.com", api_token=None,
            request_language="auto", recognition_mode="auto", provider_name="primary",
        )

    async def forbidden_network(*_args, **_kwargs):
        """Fail if oversized recognition reaches DNS or outbound transport."""
        pytest.fail("oversized source reached provider network validation")

    monkeypatch.setattr(
        newsdom_client_module, "validate_newsdom_base_url_details_async", forbidden_network
    )

    try:
        async with session_factory.begin() as session:
            session.add_all([workspace, source_record])
            await session.flush()
            source_identity = getattr(source_record, source_key.key)
        source_statement = select(type(source_record)).where(source_key == source_identity)
        if source_kind == "attachment":
            source_statement = source_statement.options(selectinload(Attachment.email))
        async with engine.connect() as connection:
            index_valid = await connection.scalar(text(
                "SELECT bool_and(index_entry.indisvalid) FROM pg_index AS index_entry "
                "JOIN pg_class AS index_object ON index_object.oid = index_entry.indexrelid "
                "JOIN pg_am AS access_method ON access_method.oid = index_object.relam "
                "WHERE index_entry.indrelid = 'email_attachments'::regclass "
                "AND access_method.amname = 'gin'"
            ))
            assert index_valid is True

        for config_resolver, expected_outcome, expected_status in (
            (no_provider, "pending", "pdf_dom_recognition_pending"),
            (configured_provider, "failed", "pdf_dom_recognition_failed"),
        ):
            async with session_factory.begin() as session:
                persisted_source = (await session.scalars(source_statement)).one()
                result = await processor(
                    session=session, **{argument_name: persisted_source},
                    config_resolver=config_resolver,
                )
                assert result == expected_outcome
                assert getattr(persisted_source, status_field) == expected_status
                if source_kind == "attachment" and expected_outcome == "failed":
                    assert persisted_source.parse_error_code == "provider_payload_size_exceeded"
            async with session_factory() as session:
                persisted_source = (await session.scalars(source_statement)).one()
                retained_bytes = base64.b64decode(getattr(persisted_source, content_field), validate=True)
                assert retained_bytes == published_pdf_bytes
                assert getattr(persisted_source, source_key.key) == source_identity
                assert getattr(persisted_source, status_field) == expected_status

        async with session_factory() as session:
            persisted_source = (await session.scalars(source_statement)).one()
            setattr(persisted_source, content_field, "")
            await session.flush()
            await session.rollback()
        async with session_factory() as session:
            persisted_source = (await session.scalars(source_statement)).one()
            retained_bytes = base64.b64decode(getattr(persisted_source, content_field), validate=True)
            assert retained_bytes == published_pdf_bytes
            assert getattr(persisted_source, source_key.key) == source_identity
            assert getattr(persisted_source, status_field) == "pdf_dom_recognition_failed"

        async with session_factory.begin() as session:
            persisted_source = (await session.scalars(source_statement)).one()
            setattr(persisted_source, status_field, "pdf_dom_recognition_pending")
            if source_kind == "attachment":
                persisted_source.parse_error_code = None
                next_source = Attachment(
                    email=persisted_source.email, filename=parsed_source.filename,
                    content=parsed_source.content, content_type="application/pdf",
                    parse_status="pdf_dom_recognition_pending", parser_key=parsed_source.parser_key,
                    parse_content_type=parsed_source.parse_content_type,
                )
            else:
                next_source = Document(
                    document_id=f"{source_identity}_next", workspace_id=persisted_source.workspace_id,
                    organization_id=persisted_source.organization_id,
                    document_name=parsed_source.filename, document_type="pdf",
                    document_content=parsed_source.content, document_status="pdf_dom_recognition_pending",
                )
            session.add(next_source)
            await session.flush()
            next_identity = getattr(next_source, source_key.key)

        resolve_count = 0

        async def fail_first_transaction(session, organization_id):
            """Abort the real first transaction; the next item must still be processed."""
            nonlocal resolve_count
            resolve_count += 1
            if resolve_count == 1:
                await session.execute(text("SELECT 1 / 0"))
            return await configured_provider(session, organization_id)

        monkeypatch.setattr(newsdom_worker_module, "AsyncSessionLocal", session_factory)
        monkeypatch.setattr(newsdom_worker_module, "engine", engine)
        worker = newsdom_worker_module.NewsdomRecognitionWorker(
            config_resolver=fail_first_transaction,
        )
        with caplog.at_level(logging.ERROR, logger="services.newsdom_worker"):
            await worker._sweep()
        assert resolve_count == 2
        error_records = [
            record for record in caplog.records
            if record.name == "services.newsdom_worker" and record.levelno >= logging.ERROR
        ]
        assert len(error_records) == 1
        assert "MissingGreenlet" not in caplog.text
        for record_identity, expected_status in (
            (source_identity, "pdf_dom_recognition_pending"),
            (next_identity, "pdf_dom_recognition_failed"),
        ):
            async with session_factory() as session:
                persisted_source = await session.get(type(source_record), record_identity)
                retained_bytes = base64.b64decode(getattr(persisted_source, content_field), validate=True)
                assert retained_bytes == published_pdf_bytes
                assert getattr(persisted_source, source_key.key) == record_identity
                assert getattr(persisted_source, status_field) == expected_status
    finally:
        await engine.dispose()


async def _persist_pending_published_pdf(session_factory, published_pdf_bytes):
    """Store the unchanged corpus using the real parser and migrated source schema."""
    parsed_source = parse_email_attachment(
        filename="earth_at_night_508.pdf", content_type="application/pdf",
        raw_content=published_pdf_bytes,
    )
    async with session_factory.begin() as session:
        source_record = Attachment(
            email=Email(
                user_id="pdf-lease-user", organization_id="pdf-lease-org",
                message_id="pdf-lease-source", sender="NASA", subject="Earth at Night",
                body="Earth at Night", date=datetime(2019, 12, 9, tzinfo=timezone.utc),
            ),
            filename=parsed_source.filename, content=parsed_source.content,
            content_type=parsed_source.content_type, parse_status=parsed_source.parse_status,
            parser_key=parsed_source.parser_key, parse_content_type=parsed_source.parse_content_type,
        )
        session.add(source_record)
        await session.flush()
        return source_record.id


@pytest.mark.parametrize("transaction_outcome", ["commit", "rollback"])
@pytest.mark.asyncio
async def test_sweep_lease_survives_item_transaction_and_releases_on_owning_backend(
    fresh_database_url, published_pdf_bytes, transaction_outcome, monkeypatch, caplog,
):
    """An unrelated pooled reader must not inherit or strand the worker's lease."""
    _run_migrations(fresh_database_url)
    engine = create_async_engine(fresh_database_url, pool_size=2, max_overflow=0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    probe_engine = create_async_engine(fresh_database_url, pool_size=1, max_overflow=0)
    probe_factory = async_sessionmaker(probe_engine, expire_on_commit=False)
    document_phase_entered = asyncio.Event()
    continue_document_phase = asyncio.Event()
    worker_backend_ids = []

    async def resolve_unavailable_provider(session, _organization_id):
        """Exercise a real per-item commit or an aborted PostgreSQL transaction."""
        worker_backend_ids.append(await session.scalar(text("SELECT pg_backend_pid()")))
        if transaction_outcome == "rollback":
            await session.execute(text("SELECT 1 / 0"))
        return None

    monkeypatch.setattr(newsdom_worker_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(newsdom_worker_module, "engine", engine)
    worker = newsdom_worker_module.NewsdomRecognitionWorker(
        config_resolver=resolve_unavailable_provider,
    )
    original_document_sweep = worker._sweep_documents

    async def pause_before_document_phase(session):
        """Let a concurrent reader borrow a pool connection between real phases."""
        document_phase_entered.set()
        await continue_document_phase.wait()
        await original_document_sweep(session)

    monkeypatch.setattr(worker, "_sweep_documents", pause_before_document_phase)
    sweep_task = None
    try:
        source_identity = await _persist_pending_published_pdf(session_factory, published_pdf_bytes)

        with caplog.at_level(logging.ERROR, logger="services.newsdom_worker"):
            sweep_task = asyncio.create_task(worker._sweep())
            await asyncio.wait_for(document_phase_entered.wait(), timeout=30)
            async with session_factory() as pooled_reader, probe_factory() as replica_probe:
                reader_backend_id = await pooled_reader.scalar(text("SELECT pg_backend_pid()"))
                try:
                    assert await newsdom_worker_module._try_acquire_sweep_lease(replica_probe) is False
                    continue_document_phase.set()
                    await asyncio.wait_for(sweep_task, timeout=30)
                    released_after_sweep = await newsdom_worker_module._try_acquire_sweep_lease(
                        replica_probe
                    )
                    if released_after_sweep:
                        await newsdom_worker_module._release_sweep_lease(replica_probe)
                    assert released_after_sweep is True, (
                        "completed sweep stranded its lease on a pooled reader: "
                        f"worker backends={worker_backend_ids}, reader backend={reader_backend_id}"
                    )
                    assert worker_backend_ids and reader_backend_id not in worker_backend_ids
                finally:
                    # Only this test's reader can inherit the known worker lock on a failing build.
                    if reader_backend_id in worker_backend_ids:
                        await newsdom_worker_module._release_sweep_lease(pooled_reader)

        async with session_factory() as session:
            retained_source = await session.get(Attachment, source_identity)
            assert retained_source.id == source_identity
            assert retained_source.parse_status == "pdf_dom_recognition_pending"
            assert base64.b64decode(retained_source.content, validate=True) == published_pdf_bytes
        worker_errors = [
            record for record in caplog.records
            if record.name == "services.newsdom_worker" and record.levelno >= logging.ERROR
        ]
        assert len(worker_errors) == (1 if transaction_outcome == "rollback" else 0)
    finally:
        continue_document_phase.set()
        if sweep_task is not None:
            await asyncio.gather(sweep_task, return_exceptions=True)
        await probe_engine.dispose()
        await engine.dispose()


@pytest.mark.parametrize(
    "exit_mode", [
        "complete", "acquire_cancel", "processing_cancel", "disconnect", "unlock_error",
        "close_before_invalidation",
    ],
)
@pytest.mark.asyncio
async def test_single_connection_sweep_releases_lease_after_completion_or_interruption(
    fresh_database_url, published_pdf_bytes, exit_mode, monkeypatch,
):
    """A real one-slot pool must recover without stranded locks or lost PDF bytes."""
    _run_migrations(fresh_database_url)
    engine = create_async_engine(
        fresh_database_url, pool_size=1, max_overflow=0, pool_timeout=1,
    )
    provider_entered = asyncio.Event()
    close_entered = asyncio.Event()
    allow_session_close = asyncio.Event()
    close_observations = []

    class ObservedCloseSession(AsyncSession):
        """Keep real SQLAlchemy exit behavior and observe its pre-rollback connection."""

        async def close(self):
            """A gated cleanup models rollback waiting for an unresponsive backend."""
            if self.info.get("lease_cleanup_probe"):
                close_observations.append(self.bind.invalidated)
                close_entered.set()
                await allow_session_close.wait()
            await super().close()

    session_factory = async_sessionmaker(engine, class_=ObservedCloseSession, expire_on_commit=False)
    probe_engine = create_async_engine(fresh_database_url, pool_size=1, max_overflow=0)
    probe_factory = async_sessionmaker(probe_engine, expire_on_commit=False)
    worker_backend_ids = []
    document_phase_calls = []
    monkeypatch.setattr(newsdom_worker_module, "engine", engine)
    monkeypatch.setattr(newsdom_worker_module, "AsyncSessionLocal", session_factory)
    original_acquire = newsdom_worker_module._try_acquire_sweep_lease
    original_release = newsdom_worker_module._release_sweep_lease

    async def acquire_then_record(session):
        """Model a lost acknowledgement only after PostgreSQL actually grants the lock."""
        acquired = await original_acquire(session)
        assert acquired is True
        worker_backend_ids.append(await session.scalar(text("SELECT pg_backend_pid()")))
        if exit_mode == "acquire_cancel":
            raise asyncio.CancelledError("controlled acquisition cancellation")
        return acquired

    async def resolve_unavailable_provider(session, _organization_id):
        """Cancel or disconnect the real work transaction without calling a model."""
        if exit_mode == "close_before_invalidation":
            session.info["lease_cleanup_probe"] = True
            provider_entered.set()
            await asyncio.Event().wait()
        if exit_mode == "processing_cancel":
            raise asyncio.CancelledError("controlled processing cancellation")
        if exit_mode == "disconnect":
            async with probe_engine.connect() as probe_connection:
                assert await probe_connection.scalar(
                    text("SELECT pg_terminate_backend(:worker_backend_id)"),
                    {"worker_backend_id": worker_backend_ids[0]},
                ) is True
            await session.scalar(text("SELECT 1"))
            pytest.fail("terminated worker backend unexpectedly remained usable")
        return None

    async def abort_unlock_transaction(session):
        """Leave release unconfirmed using an actual PostgreSQL statement failure."""
        await session.execute(text("SELECT 1 / 0"))

    worker = newsdom_worker_module.NewsdomRecognitionWorker(
        config_resolver=resolve_unavailable_provider,
    )
    original_document_sweep = worker._sweep_documents

    async def record_document_phase(session):
        """Track whether a lost lease incorrectly permits the second worker phase."""
        document_phase_calls.append(True)
        await original_document_sweep(session)

    monkeypatch.setattr(worker, "_sweep_documents", record_document_phase)
    monkeypatch.setattr(newsdom_worker_module, "_try_acquire_sweep_lease", acquire_then_record)
    if exit_mode == "unlock_error":
        monkeypatch.setattr(newsdom_worker_module, "_release_sweep_lease", abort_unlock_transaction)
    sweep_task = None
    try:
        source_identity = await _persist_pending_published_pdf(session_factory, published_pdf_bytes)
        if exit_mode == "close_before_invalidation":
            sweep_task = asyncio.create_task(worker._sweep())
            await asyncio.wait_for(provider_entered.wait(), timeout=30)
            sweep_task.cancel()
            await asyncio.wait_for(close_entered.wait(), timeout=30)
            try:
                assert close_observations == [True], "session close started before lease invalidation"
            finally:
                allow_session_close.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(sweep_task, timeout=30)
        elif exit_mode == "complete":
            await asyncio.wait_for(worker._sweep(), timeout=30)
        elif exit_mode in {"acquire_cancel", "processing_cancel"}:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(worker._sweep(), timeout=30)
        else:
            with pytest.raises(DBAPIError) as raised_error:
                await asyncio.wait_for(worker._sweep(), timeout=30)
            if exit_mode == "disconnect":
                assert raised_error.value.connection_invalidated is True
        assert len(document_phase_calls) == (1 if exit_mode in {"complete", "unlock_error"} else 0)

        async with probe_factory() as replica_probe:
            acquired_after_sweep = await original_acquire(replica_probe)
            assert acquired_after_sweep is True
            await original_release(replica_probe)
        async with session_factory() as session:
            next_backend_id = await session.scalar(text("SELECT pg_backend_pid()"))
            assert (next_backend_id == worker_backend_ids[0]) == (exit_mode == "complete")
            retained_source = await session.get(Attachment, source_identity)
            assert retained_source.parse_status == "pdf_dom_recognition_pending"
            assert base64.b64decode(retained_source.content, validate=True) == published_pdf_bytes
    finally:
        allow_session_close.set()
        if sweep_task is not None:
            sweep_task.cancel()
            await asyncio.gather(sweep_task, return_exceptions=True)
        await probe_engine.dispose()
        await engine.dispose()
