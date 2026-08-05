"""Regression tests for source-bound fallback email identities."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.email_dedupe_service import (
    canonical_email_source_content,
    source_email_fingerprint,
    strong_email_fingerprint,
)
from services.email_import_service import _email_fingerprint
from services.imap_worker import process_fetched_email


def test_source_email_fingerprint_is_stable_content_bound_and_domain_separated() -> (
    None
):
    """Hash equal sources equally while separating content and source domains."""
    first = source_email_fingerprint(b"same source")
    assert first == source_email_fingerprint(b"same source")
    assert first != source_email_fingerprint(b"different source")
    assert first != source_email_fingerprint(b"same source", source_kind="canonical")
    assert len(first) == 64


def test_canonical_source_content_excludes_collection_date() -> None:
    """Keep synthetic collection time outside direct-caller identity."""
    base = {
        "message_id": "<message@example.com>",
        "sender": "sender@example.com",
        "recipients": ["one@example.com", "two@example.com"],
        "subject": "Subject",
        "body": "Body",
        "attachments": [{"filename": "note.txt", "content": b"note"}],
    }
    first = {
        **base,
        "date": datetime.datetime(2026, 8, 4, 6, 30, tzinfo=datetime.timezone.utc),
        "date_provenance": "missing",
    }
    second = {
        **base,
        "date": datetime.datetime(2026, 8, 4, 7, 30, tzinfo=datetime.timezone.utc),
        "date_provenance": "invalid",
    }
    assert canonical_email_source_content(first) == canonical_email_source_content(
        second
    )
    assert canonical_email_source_content(first) != canonical_email_source_content(
        {**second, "body": "Different body"}
    )


def test_import_fingerprint_uses_trusted_date_or_raw_source() -> None:
    """Use strong Date evidence only when provenance is genuinely parsed."""
    persisted_date = datetime.datetime(2026, 8, 4, 6, 30, tzinfo=datetime.timezone.utc)
    fields = {
        "message_id": "",
        "sender": "sender@example.com",
        "subject": "Same subject",
        "body": "Same parsed body",
        "recipients": "recipient@example.com",
    }
    first_source = b"From: sender@example.com\r\n\r\nFirst raw body"
    second_source = b"From: sender@example.com\r\n\r\nSecond raw body"
    strong = strong_email_fingerprint(
        sender=fields["sender"],
        subject=fields["subject"],
        date=persisted_date,
        body=fields["body"],
    )
    assert strong is not None
    assert (
        _email_fingerprint(
            {**fields, "date_provenance": "parsed"},
            persisted_date,
            first_source,
        )
        == strong
    )
    for provenance in ("missing", "invalid"):
        first = _email_fingerprint(
            {**fields, "date_provenance": provenance},
            persisted_date,
            first_source,
        )
        second = _email_fingerprint(
            {**fields, "date_provenance": provenance},
            persisted_date,
            second_source,
        )
        assert first == source_email_fingerprint(first_source)
        assert second == source_email_fingerprint(second_source)
        assert first != second


def test_direct_fallback_is_collection_time_independent() -> None:
    """Give callers without raw bytes a stable non-date fallback identity."""
    parsed = {
        "message_id": "",
        "sender": "sender@example.com",
        "recipients": "recipient@example.com",
        "subject": "Direct",
        "body": "Body",
        "date_provenance": "missing",
    }
    first_time = datetime.datetime(2026, 8, 4, 6, 30, tzinfo=datetime.timezone.utc)
    second_time = first_time + datetime.timedelta(hours=1)
    assert _email_fingerprint(parsed, first_time) == _email_fingerprint(
        parsed, second_time
    )
    assert _email_fingerprint(parsed, first_time) != _email_fingerprint(
        {**parsed, "body": "Different body"}, second_time
    )


@pytest.mark.asyncio
async def test_missing_date_messages_use_raw_source_not_collection_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not merge different raw messages collected at the same instant."""
    session = AsyncMock()
    session.add = MagicMock()
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result
    monkeypatch.setattr(
        "services.imap_worker.assign_thread_id",
        AsyncMock(side_effect=("thread-first", "thread-second")),
    )
    monkeypatch.setattr(
        "services.imap_worker.is_self_sent_email",
        lambda _email, _owners: False,
    )

    collected_at = datetime.datetime(2026, 8, 4, 6, 30, tzinfo=datetime.timezone.utc)
    common = {
        "subject": "Same subject",
        "date": collected_at,
        "date_provenance": "missing",
        "sender": "sender@example.com",
        "recipients": "recipient@example.com",
        "message_id": "",
    }
    first_source = b"From: sender@example.com\r\n\r\nFirst raw body"
    second_source = b"From: sender@example.com\r\n\r\nSecond raw body"

    first_email = await process_fetched_email(
        session,
        {**common, "body": "First body"},
        "owner@example.com",
        "org-acme",
        source_content=first_source,
    )
    second_email = await process_fetched_email(
        session,
        {**common, "body": "Second body"},
        "owner@example.com",
        "org-acme",
        source_content=second_source,
    )

    assert first_email.date == collected_at
    assert second_email.date == collected_at
    assert first_email.fingerprint == source_email_fingerprint(first_source)
    assert second_email.fingerprint == source_email_fingerprint(second_source)
    assert first_email.fingerprint != second_email.fingerprint
