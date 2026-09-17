import datetime

from services.email_dedupe_service import source_email_fingerprint, strong_email_fingerprint
from services.email_import_service import _dedupe_review_reason, _email_fingerprint


_DATE = datetime.datetime(2026, 9, 17, 6, 30, tzinfo=datetime.timezone.utc)
_SOURCE = b"From: sender@example.com\r\nTo: recipient@example.com\r\nSubject: Plan\r\n\r\nBody"
_COMPLETE = {
    "sender": "sender@example.com",
    "recipients": "recipient@example.com",
    "subject": "Plan",
    "body": "Body",
    "date": _DATE,
    "date_provenance": "parsed",
}


def test_import_metadata_strong_fingerprint_requires_recipient_evidence() -> None:
    expected_strong = strong_email_fingerprint(
        sender=_COMPLETE["sender"],
        subject=_COMPLETE["subject"],
        date=_DATE,
        body=_COMPLETE["body"],
    )
    assert expected_strong is not None
    assert _email_fingerprint(dict(_COMPLETE), _DATE, _SOURCE) == expected_strong

    incomplete = {**_COMPLETE, "recipients": ""}
    assert _email_fingerprint(incomplete, _DATE, _SOURCE) == source_email_fingerprint(
        _SOURCE,
        source_kind="raw",
    )


def test_import_review_reason_tracks_withheld_strong_metadata_evidence() -> None:
    assert _dedupe_review_reason(dict(_COMPLETE)) is None
    assert _dedupe_review_reason({**_COMPLETE, "recipients": ""}) == (
        "dedupe_review_required"
    )
    assert _dedupe_review_reason({**_COMPLETE, "date_provenance": "invalid"}) == (
        "dedupe_review_required"
    )
