import datetime
from types import SimpleNamespace

import pytest

from services.email_dedupe_service import (
    EmailDedupeCandidate,
    candidate_strong_fingerprint,
    email_strong_fingerprint,
)


_COMPLETE = {
    "sender": "sender@example.com",
    "recipients": "recipient@example.com",
    "subject": "Quarterly plan",
    "date": datetime.datetime(2026, 9, 17, 6, 0, tzinfo=datetime.timezone.utc),
    "body": "Please review the attached plan.",
}


def test_candidate_strong_fingerprint_requires_complete_metadata() -> None:
    candidate = EmailDedupeCandidate(
        candidate_key="candidate-1",
        date_provenance="parsed",
        **_COMPLETE,
    )

    assert candidate_strong_fingerprint(candidate) is not None


@pytest.mark.parametrize("missing_field", ["sender", "recipients", "subject", "body"])
def test_candidate_strong_fingerprint_withholds_incomplete_metadata(
    missing_field: str,
) -> None:
    values = dict(_COMPLETE)
    values[missing_field] = ""
    candidate = EmailDedupeCandidate(
        candidate_key=f"missing-{missing_field}",
        date_provenance="parsed",
        **values,
    )

    assert candidate_strong_fingerprint(candidate) is None


def test_stored_email_strong_fingerprint_withholds_incomplete_metadata() -> None:
    stored = SimpleNamespace(
        date_provenance="parsed",
        **{**_COMPLETE, "recipients": None},
    )

    assert email_strong_fingerprint(stored) is None
