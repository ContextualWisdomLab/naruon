"""Focused contracts for email metadata provenance classification."""

import datetime

from services.email_parser import parse_eml_bytes


def _eml_with(headers: str) -> bytes:
    """Build minimal EML bytes with the given header block and a plain body."""
    return (headers.strip("\r\n") + "\n\nBody text.").encode("utf-8")


def test_parse_eml_marks_valid_date_as_parsed_with_original_header_date() -> None:
    """A valid Date header remains the genuine timezone-aware storage value."""
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <parsed-date@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Valid date
Date: Mon, 27 Apr 2026 10:00:00 +0000"""
        )
    )

    expected = datetime.datetime(2026, 4, 27, 10, 0, 0, tzinfo=datetime.timezone.utc)
    assert parsed["date_provenance"] == "parsed"
    assert parsed["header_date"] == expected
    assert parsed["date"] == expected


def test_parse_eml_marks_missing_date_without_promoting_the_fallback() -> None:
    """A missing Date uses storage fallback without inventing sender evidence."""
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <missing-date@test.com>
From: sender@test.com
To: recipient@test.com
Subject: No date header"""
        )
    )

    assert parsed["date_provenance"] == "missing"
    assert parsed["header_date"] is None
    assert parsed["date"].tzinfo is not None


def test_parse_eml_marks_invalid_date_without_promoting_the_fallback() -> None:
    """An invalid Date uses storage fallback without inventing sender evidence."""
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <invalid-date@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Unparseable date
Date: not-a-real-date"""
        )
    )

    assert parsed["date_provenance"] == "invalid"
    assert parsed["header_date"] is None
    assert parsed["date"].tzinfo is not None


def test_parse_eml_marks_whitespace_only_date_as_missing() -> None:
    """A whitespace-only Date is missing rather than malformed evidence."""
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <whitespace-date@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Whitespace-only date
Date:    """
        )
    )

    assert parsed["date_provenance"] == "missing"
    assert parsed["header_date"] is None
    assert parsed["date"].tzinfo is not None


def test_parse_eml_normalizes_minus_zero_zone_to_utc() -> None:
    """RFC 5322 -0000 dates remain timezone-aware for storage and comparison."""
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <minus-zero-zone@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Minus-zero timezone
Date: Sun, 01 Jan 2023 12:00:00 -0000"""
        )
    )

    assert parsed["date_provenance"] == "parsed"
    assert parsed["header_date"] is not None
    assert parsed["header_date"].tzinfo is not None
    assert parsed["header_date"].utcoffset() == datetime.timedelta(0)
    assert parsed["date"].tzinfo is not None


def test_parse_eml_marks_embedded_message_id_provenance() -> None:
    """A non-empty embedded Message-ID is identified as sender evidence."""
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <embedded-id@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Has message id
Date: Mon, 27 Apr 2026 10:00:00 +0000"""
        )
    )

    assert parsed["message_id_provenance"] == "embedded"


def test_parse_eml_marks_missing_message_id_provenance() -> None:
    """A missing Message-ID is explicitly classified as absent evidence."""
    parsed = parse_eml_bytes(
        _eml_with(
            """From: sender@test.com
To: recipient@test.com
Subject: No message id
Date: Mon, 27 Apr 2026 10:00:00 +0000"""
        )
    )

    assert parsed["message_id"] == ""
    assert parsed["message_id_provenance"] == "missing"
