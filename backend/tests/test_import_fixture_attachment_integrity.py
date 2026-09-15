"""Regression coverage for fixture-import attachment enrichment failures."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest

import import_fixtures


class _NoExistingEmailResult:
    def scalar_one_or_none(self):
        return None


class _RecordingSession:
    def __init__(self):
        self.database_started = False
        self.added = None
        self.committed = False

    async def execute(self, _query):
        self.database_started = True
        return _NoExistingEmailResult()

    def add(self, obj):
        self.added = obj

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_attachment_survives_embedding_failure_before_database_transaction(tmp_path):
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
        assert session.database_started is False
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
    assert session.committed is True
    assert session.added is not None
    assert len(session.added.attachments) == 1
    attachment = session.added.attachments[0]
    assert attachment.filename == "evidence.txt"
    assert attachment.content == "attachment source content"
    assert attachment.embedding is None
