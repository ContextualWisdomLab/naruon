"""Regression coverage for fixture-import attachment enrichment failures."""

import datetime
import uuid
from unittest.mock import AsyncMock, patch

import pytest

import import_fixtures


class _QueryResult:
    def __init__(self, existing=None):
        self._existing = existing

    def scalar_one_or_none(self):
        return self._existing


class _RecordingSession:
    def __init__(self, results=None):
        self.database_transaction_active = False
        self.added = None
        self.committed = False
        self.rollback_count = 0
        self._results = iter(results or [None, None])

    async def execute(self, _query):
        self.database_transaction_active = True
        return _QueryResult(next(self._results))

    def add(self, obj):
        self.added = obj

    async def commit(self):
        self.committed = True
        self.database_transaction_active = False

    async def rollback(self):
        self.rollback_count += 1
        self.database_transaction_active = False


@pytest.mark.asyncio
async def test_attachment_survives_embedding_failure_outside_database_transaction(
    tmp_path,
):
    eml_file = tmp_path / "attachment-fallback.eml"
    eml_file.write_text("Message-ID: <attachment-fallback@example.com>\n\nBody")
    parsed = {
        "message_id": "<attachment-fallback@example.com>",
        "sender": "sender@example.com",
        "recipients": "user@example.com",
        "subject": "Attachment fallback",
        "date": datetime.datetime.now(datetime.timezone.utc),
        "body": "Body",
        "attachments": [
            {
                "filename": "evidence.txt",
                "content": "attachment source content",
            }
        ],
    }
    session = _RecordingSession()

    async def generate_embedding(text: str):
        assert session.database_transaction_active is False
        if text == "attachment source content":
            raise RuntimeError("embedding provider unavailable")
        return [0.0] * import_fixtures.EMBEDDING_DIMENSION

    with patch.object(import_fixtures, "parse_eml", return_value=parsed), patch.object(
        import_fixtures,
        "generate_fixture_embedding",
        side_effect=generate_embedding,
    ), patch.object(
        import_fixtures,
        "assign_thread_id",
        new_callable=AsyncMock,
        return_value="attachment-fallback-thread",
    ):
        imported = await import_fixtures.import_eml_file(session, eml_file)

    assert imported is True
    assert session.rollback_count == 1
    assert session.committed is True
    assert session.added is not None
    assert len(session.added.attachments) == 1
    attachment = session.added.attachments[0]
    assert attachment.filename == "evidence.txt"
    assert attachment.content == "attachment source content"
    assert attachment.embedding is None


@pytest.mark.asyncio
async def test_duplicate_fixture_skips_enrichment_and_releases_read_transaction(tmp_path):
    eml_file = tmp_path / "duplicate.eml"
    eml_file.write_text("Message-ID: <duplicate@example.com>\n\nBody")
    parsed = {
        "message_id": "<duplicate@example.com>",
        "sender": "sender@example.com",
        "recipients": "user@example.com",
        "subject": "Duplicate",
        "date": datetime.datetime.now(datetime.timezone.utc),
        "body": "Body",
        "attachments": [],
    }
    session = _RecordingSession(results=[object()])

    with patch.object(import_fixtures, "parse_eml", return_value=parsed), patch.object(
        import_fixtures,
        "generate_fixture_embedding",
        new_callable=AsyncMock,
    ) as embedding_mock, patch.object(
        import_fixtures,
        "assign_thread_id",
        new_callable=AsyncMock,
    ) as thread_mock:
        imported = await import_fixtures.import_eml_file(session, eml_file)

    assert imported is False
    assert session.rollback_count == 1
    assert session.database_transaction_active is False
    assert session.committed is False
    embedding_mock.assert_not_awaited()
    thread_mock.assert_not_awaited()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_attachment_embedding_failure_persists_source_in_real_postgres(tmp_path):
    """Persist nullable derived enrichment and prove Email attachment cascade."""
    from asyncpg.exceptions import (
        InvalidAuthorizationSpecificationError,
        InvalidPasswordError,
    )
    from sqlalchemy import select, text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload

    from core.config import settings
    from db.models import Attachment, Base, Email

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    message_id = f"<attachment-postgres-{uuid.uuid4().hex}@example.com>"
    attachment_filename = f"evidence-{uuid.uuid4().hex}.txt"
    attachment_content = "authoritative attachment source content"
    eml_file = tmp_path / "attachment-postgres.eml"
    eml_file.write_text(f"Message-ID: {message_id}\n\nBody")
    parsed = {
        "message_id": message_id,
        "sender": "sender@example.com",
        "recipients": "user@example.com",
        "subject": "Attachment PostgreSQL acceptance",
        "date": datetime.datetime.now(datetime.timezone.utc),
        "body": "Body",
        "attachments": [
            {
                "filename": attachment_filename,
                "content": attachment_content,
            }
        ],
    }

    async def generate_embedding(text_value: str):
        if text_value == attachment_content:
            raise RuntimeError("embedding provider unavailable")
        return [0.0] * import_fixtures.EMBEDDING_DIMENSION

    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            with patch.object(
                import_fixtures, "parse_eml", return_value=parsed
            ), patch.object(
                import_fixtures,
                "generate_fixture_embedding",
                side_effect=generate_embedding,
            ), patch.object(
                import_fixtures,
                "assign_thread_id",
                new_callable=AsyncMock,
                return_value="attachment-postgres-thread",
            ):
                imported = await import_fixtures.import_eml_file(session, eml_file)

        assert imported is True

        async with session_factory() as session:
            persisted_email = (
                await session.execute(
                    select(Email)
                    .options(selectinload(Email.attachments))
                    .where(
                        Email.message_id == message_id,
                        Email.user_id == import_fixtures.IMPORT_USER_ID,
                        Email.organization_id == import_fixtures.IMPORT_ORGANIZATION_ID,
                    )
                )
            ).scalar_one()
            assert len(persisted_email.attachments) == 1
            persisted_attachment = persisted_email.attachments[0]
            attachment_id = persisted_attachment.id
            assert persisted_attachment.filename == attachment_filename
            assert persisted_attachment.content == attachment_content
            assert persisted_attachment.embedding is None

            await session.delete(persisted_email)
            await session.commit()

        async with session_factory() as session:
            assert await session.get(Email, persisted_email.id) is None
            assert await session.get(Attachment, attachment_id) is None
    except (
        InvalidAuthorizationSpecificationError,
        InvalidPasswordError,
        OperationalError,
        OSError,
    ) as exc:
        pytest.skip(f"PostgreSQL smoke database unavailable: {exc}")
    finally:
        await engine.dispose()
