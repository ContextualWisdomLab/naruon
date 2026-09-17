import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.email_dedupe_service import source_email_fingerprint
from services.imap_worker import process_fetched_email


@pytest.mark.asyncio
async def test_imap_withholds_metadata_strong_fingerprint_without_recipients(
    monkeypatch,
) -> None:
    raw_message = b"From: sender@example.com\r\nSubject: Plan\r\n\r\nBody"
    email_data = {
        "message_id": "<imap-boundary@example.com>",
        "sender": "sender@example.com",
        "recipients": "",
        "subject": "Plan",
        "date": datetime.datetime(2026, 9, 17, 6, 45, tzinfo=datetime.timezone.utc),
        "date_provenance": "parsed",
        "body": "Body",
    }

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=query_result)
    session.flush = AsyncMock()

    monkeypatch.setattr(
        "services.imap_worker.assign_thread_id",
        AsyncMock(return_value="thread-boundary"),
    )

    imported = await process_fetched_email(
        session,
        email_data,
        "user-1",
        "org-1",
        source_content=raw_message,
    )

    assert imported.fingerprint == source_email_fingerprint(
        raw_message,
        source_kind="raw",
    )
