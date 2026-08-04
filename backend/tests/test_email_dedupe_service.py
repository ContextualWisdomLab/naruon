from datetime import datetime, timezone

from services.email_dedupe_service import (
    EmailDedupeCandidate,
    candidate_message_lookup_values,
    _date_to_fingerprint_value,
    strong_email_fingerprint,
    candidate_strong_fingerprint,
    email_strong_fingerprint,
    content_email_fingerprint,
    candidate_content_fingerprint,
    email_content_fingerprint,
    classify_dedupe_decision,
    resolve_candidate_disposition,
)
from db.models import Email


def _email_row(**overrides):
    fields = dict(
        id=100,
        user_id="user-1",
        organization_id="org-1",
        message_id=None,
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        date_provenance="parsed",
        body="Hello world",
    )
    fields.update(overrides)
    return Email(**fields)

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
        date_provenance="parsed",
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


def test_email_strong_fingerprint_gated_to_parsed_date_provenance():
    """A stored row seeds a strong fingerprint only when its date is genuine.

    naruon#1086: rows whose ``date`` is a synthetic collection-time fallback
    (missing/invalid) or unknown-provenance (stored before tracking) must not
    seed a strong auto-dedupe fingerprint, even though sender/subject/body/date
    are populated.
    """
    fields = dict(
        id=2,
        user_id="user-1",
        organization_id="org-1",
        message_id="msg-2",
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        body="Hello world",
    )
    assert email_strong_fingerprint(Email(**fields, date_provenance="parsed")) is not None
    for provenance in ("missing", "invalid", "unknown"):
        assert email_strong_fingerprint(Email(**fields, date_provenance=provenance)) is None


# --- content fingerprint (date-independent identity signal, naruon#1086) ---

def test_content_email_fingerprint_none_without_body():
    assert content_email_fingerprint(sender="a@x", subject="S", body=None) is None
    assert content_email_fingerprint(sender="a@x", subject="S", body="") is None


def test_content_email_fingerprint_is_date_independent_and_not_the_strong_one():
    """The content fingerprint ignores the Date; the strong one includes it."""
    content = content_email_fingerprint(
        sender="sender@example.com", subject="Subject", body="Hello world"
    )
    strong = strong_email_fingerprint(
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        body="Hello world",
    )
    assert content is not None
    assert content != strong
    # Same content, different Date -> identical content fingerprint.
    candidate_a = EmailDedupeCandidate(
        candidate_key="a",
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        body="Hello world",
    )
    candidate_b = EmailDedupeCandidate(
        candidate_key="b",
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2024, 6, 6, tzinfo=timezone.utc),
        body="Hello world",
    )
    assert candidate_content_fingerprint(candidate_a) == candidate_content_fingerprint(
        candidate_b
    )
    assert email_content_fingerprint(_email_row()) == content


def test_email_content_fingerprint_none_without_body():
    assert email_content_fingerprint(_email_row(body=None)) is None


# --- Fellegi-Sunter (1969) three-zone classifier ---

def test_auto_link_on_matching_normalized_message_id():
    # Bracketed vs bare Message-ID normalize equal; content is irrelevant here.
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        message_id="<shared@x>",
        sender="other@example.com",
        subject="Totally different",
        body="unrelated body",
    )
    existing = _email_row(message_id="shared@x")
    assert classify_dedupe_decision(candidate, existing) == "auto_link"


def test_auto_link_on_genuine_strong_match_without_message_id():
    date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        sender="sender@example.com",
        subject="Subject",
        date=date,
        body="Hello world",
        date_provenance="parsed",
    )
    existing = _email_row(date=date, date_provenance="parsed")
    assert classify_dedupe_decision(candidate, existing) == "auto_link"


def test_review_required_when_candidate_date_provenance_is_untrusted():
    date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        sender="sender@example.com",
        subject="Subject",
        date=date,
        body="Hello world",
        date_provenance="missing",
    )
    existing = _email_row(date=date, date_provenance="parsed")
    # Same content, but the candidate's Date is synthetic -> no strong match, no
    # Message-ID link -> clerical-review band, not a silent merge.
    assert classify_dedupe_decision(candidate, existing) == "review_required"


def test_review_required_when_existing_date_provenance_is_untrusted():
    date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        sender="sender@example.com",
        subject="Subject",
        date=date,
        body="Hello world",
        date_provenance="parsed",
    )
    existing = _email_row(date=date, date_provenance="unknown")
    assert classify_dedupe_decision(candidate, existing) == "review_required"


def test_review_required_when_content_matches_but_dates_differ_untrusted():
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        sender="sender@example.com",
        subject="Subject",
        date=datetime(2024, 6, 6, tzinfo=timezone.utc),
        body="Hello world",
        date_provenance="invalid",
    )
    existing = _email_row(
        date=datetime(2023, 1, 1, tzinfo=timezone.utc), date_provenance="unknown"
    )
    assert classify_dedupe_decision(candidate, existing) == "review_required"


def test_distinct_on_different_content_and_no_identity_link():
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        message_id="only-on-candidate@x",
        sender="different@example.com",
        subject="Different",
        body="different body",
        date_provenance="parsed",
    )
    existing = _email_row(message_id="only-on-existing@x")
    assert classify_dedupe_decision(candidate, existing) == "distinct"


def test_distinct_when_candidate_has_no_body():
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        sender="sender@example.com",
        subject="Subject",
        body=None,
        date_provenance="parsed",
    )
    existing = _email_row()
    assert classify_dedupe_decision(candidate, existing) == "distinct"


def test_resolve_disposition_empty_corpus_is_distinct():
    candidate = EmailDedupeCandidate(candidate_key="c", message_id="m@x", body="b")
    assert resolve_candidate_disposition(candidate, []) == ("distinct", None)


def test_resolve_disposition_all_distinct_returns_distinct_none():
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        message_id="only-on-candidate@x",
        sender="different@example.com",
        subject="Different",
        body="different body",
        date_provenance="parsed",
    )
    rows = [_email_row(id=1, message_id="a@x"), _email_row(id=2, message_id="b@x")]
    assert resolve_candidate_disposition(candidate, rows) == ("distinct", None)


def test_resolve_disposition_returns_review_row_when_only_content_matches():
    date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        sender="sender@example.com",
        subject="Subject",
        date=date,
        body="Hello world",
        date_provenance="missing",  # synthetic Date -> no strong/A1 link
    )
    unrelated = _email_row(id=1, message_id="unrelated@x", body="different body")
    content_match = _email_row(id=2, date=date, date_provenance="parsed")
    decision, matched = resolve_candidate_disposition(candidate, [unrelated, content_match])
    assert decision == "review_required"
    assert matched is content_match


def test_resolve_disposition_a1_link_dominates_earlier_a2_review():
    # A review_required content match appears BEFORE the auto_link row in the
    # corpus; Fellegi-Sunter A1 must still win regardless of iteration order.
    date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    candidate = EmailDedupeCandidate(
        candidate_key="c",
        message_id="<shared@x>",
        sender="sender@example.com",
        subject="Subject",
        date=date,
        body="Hello world",
        date_provenance="missing",
    )
    content_only = _email_row(id=1, date=date, date_provenance="unknown")
    id_link = _email_row(id=2, message_id="shared@x", body="totally different")
    decision, matched = resolve_candidate_disposition(candidate, [content_only, id_link])
    assert decision == "auto_link"
    assert matched is id_link


def test_resolve_disposition_first_auto_link_wins():
    candidate = EmailDedupeCandidate(
        candidate_key="c", message_id="<shared@x>", body="b", date_provenance="parsed"
    )
    first = _email_row(id=1, message_id="shared@x")
    second = _email_row(id=2, message_id="shared@x")
    decision, matched = resolve_candidate_disposition(candidate, [first, second])
    assert decision == "auto_link"
    assert matched is first
