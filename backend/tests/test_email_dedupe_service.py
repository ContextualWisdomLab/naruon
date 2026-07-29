from datetime import datetime, timezone

from services.email_dedupe_service import (
    EmailDedupeCandidate,
    candidate_message_lookup_values,
    _date_to_fingerprint_value,
    strong_email_fingerprint,
    candidate_strong_fingerprint,
    email_strong_fingerprint,
)
from db.models import Email

def test_candidate_message_lookup_values_basic():
    candidate = EmailDedupeCandidate(
        candidate_key="key",
        message_id="test-id@example.com"
    )
    result = candidate_message_lookup_values(candidate)
    assert result == {"test-id@example.com", "<test-id@example.com>"}

def test_candidate_message_lookup_values_none():
    candidate = EmailDedupeCandidate(
        candidate_key="key",
        message_id=None
    )
    result = candidate_message_lookup_values(candidate)
    assert result == set()

def test_candidate_message_lookup_values_empty():
    candidate = EmailDedupeCandidate(
        candidate_key="key",
        message_id=""
    )
    result = candidate_message_lookup_values(candidate)
    assert result == set()

def test_candidate_message_lookup_values_with_brackets():
    candidate = EmailDedupeCandidate(
        candidate_key="key",
        message_id="<test-id@example.com>"
    )
    result = candidate_message_lookup_values(candidate)
    assert result == {"test-id@example.com", "<test-id@example.com>"}

def test_date_to_fingerprint_value_none():
    assert _date_to_fingerprint_value(None) == ""

def test_date_to_fingerprint_value_valid():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert _date_to_fingerprint_value(dt) == "2023-01-01T12:00:00+00:00"

def test_strong_email_fingerprint_no_body():
    result = strong_email_fingerprint(
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        body=None
    )
    assert result is None

def test_strong_email_fingerprint_valid():
    result = strong_email_fingerprint(
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        body="Hello world"
    )
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0

def test_candidate_strong_fingerprint():
    candidate = EmailDedupeCandidate(
        candidate_key="key",
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        body="Hello world"
    )
    result1 = candidate_strong_fingerprint(candidate)

    result2 = strong_email_fingerprint(
        sender=candidate.sender,
        subject=candidate.subject,
        date=candidate.date,
        body=candidate.body,
    )
    assert result1 == result2
    assert result1 is not None

def test_email_strong_fingerprint():
    email = Email(
        id=1,
        user_id="user-1",
        organization_id="org-1",
        message_id="msg-1",
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        body="Hello world"
    )
    result1 = email_strong_fingerprint(email)

    result2 = strong_email_fingerprint(
        sender=email.sender,
        subject=email.subject,
        date=email.date,
        body=email.body,
    )
    assert result1 == result2
    assert result1 is not None
