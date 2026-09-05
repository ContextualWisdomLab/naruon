"""Real published PDF retention on a migrated database, without recognition claims."""

import base64
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
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
