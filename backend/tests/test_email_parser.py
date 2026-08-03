import datetime
import os
import tempfile
from email.message import Message
from unittest.mock import patch

import pytest
from services.email_parser import (
    _extract_thread_id,
    _sanitize_nul,
    parse_eml,
    parse_eml_bytes,
)
from services.exceptions import EmailParseError


def test_parse_eml_basic():
    eml_content = b"""Message-ID: <123@test.com>
From: test@test.com\x00
To: recipient@test.com
Subject: Hello\x00World
Date: Mon, 27 Apr 2026 10:00:00 +0000

This is a test email.\x00"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["message_id"] == "<123@test.com>"
        assert parsed["sender"] == "test@test.com"  # NUL removed
        assert parsed["subject"] == "HelloWorld"  # NUL removed
        assert "This is a test email." in parsed["body"]
        assert "\x00" not in parsed["body"]
    finally:
        os.unlink(temp_path)


def test_parse_eml_multipart_html_fallback():
    eml_content = b"""Message-ID: <multi@test.com>
From: multi@test.com
To: recipient@test.com
Subject: Multipart HTML
Date: Mon, 27 Apr 2026 10:00:00 +0000
Content-Type: multipart/alternative; boundary="boundary-string"

--boundary-string
Content-Type: text/html; charset="utf-8"

<p>This is HTML content</p>
--boundary-string--"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["body"] == "This is HTML content"
        assert parsed["body_content_type"] == "text/html"
        assert parsed["body_parse_content"] == "<p>This is HTML content</p>"
    finally:
        os.unlink(temp_path)


def test_parse_eml_strips_active_html_from_display_fields():
    eml_content = b"""Message-ID: <xss@test.com>
From: Attacker <attacker@example.com>
To: recipient@test.com
Subject: <img src=x onerror=alert('subject')>Launch
Date: Mon, 27 Apr 2026 10:00:00 +0000
Content-Type: text/html; charset="utf-8"

<html><body>Hello<script>alert('body')</script><img src=x onerror=alert('body')></body></html>"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["subject"] == "Launch"
        assert parsed["body"] == "Hello"
        assert "<" not in parsed["body"]
        assert "script" not in parsed["body"].lower()
        assert parsed["message_id"] == "<xss@test.com>"
        assert parsed["sender"] == "Attacker <attacker@example.com>"
    finally:
        os.unlink(temp_path)


def test_parse_eml_strips_active_html_from_address_display_fields():
    eml_content = b"""Message-ID: <headers@test.com>
From: "<img src=x onerror=alert(1)>" <attacker@example.com>
To: "<script>alert(1)</script>" <recipient@test.com>
Reply-To: "&lt;svg onload=alert(1)&gt;" <reply@test.com>
Subject: Header display safety
Date: Mon, 27 Apr 2026 10:00:00 +0000

Plain body"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["sender"] == "attacker@example.com"
        assert parsed["recipients"] == "recipient@test.com"
        assert parsed["reply_to"] == "reply@test.com"
    finally:
        os.unlink(temp_path)


def test_parse_eml_strips_active_html_from_attachment_display_fields():
    eml_content = b"""Message-ID: <attachment-xss@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Attachment display safety
Date: Mon, 27 Apr 2026 10:00:00 +0000
Content-Type: multipart/mixed; boundary="mixed-boundary"

--mixed-boundary
Content-Type: text/plain; charset="utf-8"

See attached.
--mixed-boundary
Content-Type: text/plain; charset="utf-8"
Content-Disposition: attachment; filename="<img src=x onerror=alert(1)>.txt"

<script>alert(1)</script>report
--mixed-boundary--"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["attachments"] == [
            {
                "filename": ".txt",
                "content": "report",
                "content_type": "text/plain",
                "parse_content": "<script>alert(1)</script>report",
                "parse_content_type": "text/plain",
                "parser_key": "plain_text",
                "parse_status": "parsed",
                "parse_error_code": None,
            }
        ]
    finally:
        os.unlink(temp_path)


def test_parse_eml_extracts_supported_and_unsupported_attachment_metadata():
    eml_content = b"""Message-ID: <attachment-types@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Attachment types
Date: Mon, 27 Apr 2026 10:00:00 +0000
Content-Type: multipart/mixed; boundary="mixed-boundary"

--mixed-boundary
Content-Type: text/plain; charset="utf-8"

See attached.
--mixed-boundary
Content-Type: text/html; charset="utf-8"
Content-Disposition: attachment; filename="page.html"

<h1>Launch</h1><p>Ship</p>
--mixed-boundary
Content-Type: text/markdown; charset="utf-8"
Content-Disposition: attachment; filename="plan.md"

# Plan

Ship graph
--mixed-boundary
Content-Type: application/json; charset="utf-8"
Content-Disposition: attachment; filename="status.json"

{"project":"Launch"}
--mixed-boundary
Content-Type: text/csv; charset="utf-8"
Content-Disposition: attachment; filename="status.csv"

name,status
Launch,Ready
--mixed-boundary
Content-Type: application/xml; charset="utf-8"
Content-Disposition: attachment; filename="status.xml"

<root>Launch</root>
--mixed-boundary
Content-Type: text/calendar; charset="utf-8"
Content-Disposition: attachment; filename="invite.ics"

BEGIN:VCALENDAR
SUMMARY:Launch
END:VCALENDAR
--mixed-boundary
Content-Type: application/pdf
Content-Disposition: attachment; filename="contract.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjcK
--mixed-boundary--"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["attachments"] == [
            {
                "filename": "page.html",
                "content": "Launch Ship",
                "content_type": "text/html",
                "parse_content": "<h1>Launch</h1><p>Ship</p>",
                "parse_content_type": "text/html",
                "parser_key": "html",
                "parse_status": "parsed",
                "parse_error_code": None,
            },
            {
                "filename": "plan.md",
                "content": "# Plan Ship graph",
                "content_type": "text/markdown",
                "parse_content": "# Plan\n\nShip graph",
                "parse_content_type": "text/markdown",
                "parser_key": "markdown",
                "parse_status": "parsed",
                "parse_error_code": None,
            },
            {
                "filename": "status.json",
                "content": '{"project":"Launch"}',
                "content_type": "application/json",
                "parse_content": '{"project":"Launch"}',
                "parse_content_type": "application/json",
                "parser_key": "json",
                "parse_status": "parsed",
                "parse_error_code": None,
            },
            {
                "filename": "status.csv",
                "content": "name,status Launch,Ready",
                "content_type": "text/csv",
                "parse_content": "name,status\nLaunch,Ready",
                "parse_content_type": "text/csv",
                "parser_key": "csv",
                "parse_status": "parsed",
                "parse_error_code": None,
            },
            {
                "filename": "status.xml",
                "content": "Launch",
                "content_type": "application/xml",
                "parse_content": "<root>Launch</root>",
                "parse_content_type": "application/xml",
                "parser_key": "xml",
                "parse_status": "parsed",
                "parse_error_code": None,
            },
            {
                "filename": "invite.ics",
                "content": "BEGIN:VCALENDAR SUMMARY:Launch END:VCALENDAR",
                "content_type": "text/calendar",
                "parse_content": "BEGIN:VCALENDAR\nSUMMARY:Launch\nEND:VCALENDAR",
                "parse_content_type": "text/calendar",
                "parser_key": "calendar",
                "parse_status": "parsed",
                "parse_error_code": None,
            },
            {
                "filename": "contract.pdf",
                # Deferred to the NewsDOM worker: the raw PDF bytes are retained
                # as a base64 payload (round-trips the fixture's %PDF-1.7\n) so
                # the worker can recognize them later.
                "content": "JVBERi0xLjcK",
                "content_type": "application/pdf",
                "parse_content": "",
                "parse_content_type": "application/pdf",
                "parser_key": "pdf",
                "parse_status": "pdf_dom_recognition_pending",
                "parse_error_code": None,
            },
        ]
    finally:
        os.unlink(temp_path)


def test_parse_eml_missing_and_malformed_date():
    eml_content1 = b"""Message-ID: <nodate@test.com>
From: test@test.com
To: recipient@test.com
Subject: No Date

Test."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content1)
        temp_path1 = f.name

    eml_content2 = b"""Message-ID: <baddate@test.com>
From: test@test.com
To: recipient@test.com
Subject: Bad Date
Date: Invalid-Date-Format

Test."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content2)
        temp_path2 = f.name

    try:
        # Missing date
        parsed1 = parse_eml(temp_path1)
        assert isinstance(parsed1["date"], datetime.datetime)

        # Malformed date
        parsed2 = parse_eml(temp_path2)
        assert isinstance(parsed2["date"], datetime.datetime)
    finally:
        os.unlink(temp_path1)
        os.unlink(temp_path2)


def test_parse_eml_io_error():
    with pytest.raises(EmailParseError):
        parse_eml("/path/to/nonexistent/file.eml")


def test_parse_eml_thread_id():
    # 1. Has References
    eml1 = b"""Message-ID: <msg1@test.com>
References: <ref1@test.com> <ref2@test.com>
From: test@test.com
To: user@test.com
Subject: Test

Test"""
    # 2. No References, has In-Reply-To
    eml2 = b"""Message-ID: <msg2@test.com>
In-Reply-To: <ref3@test.com>
From: test@test.com
To: user@test.com
Subject: Test

Test"""
    # 3. Neither -> use Message-ID
    eml3 = b"""Message-ID: <msg3@test.com>
From: test@test.com
To: user@test.com
Subject: Test

Test"""

    for i, content in enumerate([eml1, eml2, eml3]):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
            f.write(content)
            temp_path = f.name
        try:
            parsed = parse_eml(temp_path)
            if i == 0:
                assert parsed["thread_id"] == "<ref1@test.com>"
            elif i == 1:
                assert parsed["thread_id"] == "<ref3@test.com>"
            elif i == 2:
                assert parsed["thread_id"] == "<msg3@test.com>"
        finally:
            os.unlink(temp_path)


def test_extract_thread_id_uses_first_reference_from_long_header():
    msg = Message()
    msg["References"] = " ".join(
        ["<root@test.com>", *(f"<ref-{index}@test.com>" for index in range(200))]
    )
    msg["In-Reply-To"] = "<reply@test.com>"

    assert _extract_thread_id(msg, "<message@test.com>") == "<root@test.com>"


def test_parse_eml_extracts_reply_to_header():
    eml_content = b"""Message-ID: <reply-to@test.com>
From: Sender Name <sender@test.com>
Reply-To: Reply Target <reply-target@test.com>
To: user@test.com
Subject: Reply-To Test

Test"""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as f:
        f.write(eml_content)
        temp_path = f.name

    try:
        parsed = parse_eml(temp_path)
        assert parsed["reply_to"] == "Reply Target <reply-target@test.com>"
    finally:
        os.unlink(temp_path)


def test_parse_eml_mocked_oserror():
    with patch("builtins.open", side_effect=OSError("Mocked OS Error")):
        with pytest.raises(
            EmailParseError,
            match=r"Failed to read file dummy\.eml: Mocked OS Error",
        ):
            parse_eml("dummy.eml")


def test_sanitize_nul():
    # Normal string
    assert _sanitize_nul("hello world") == "hello world"

    # Strings with NUL characters
    assert _sanitize_nul("hello\x00world") == "helloworld"
    assert _sanitize_nul("\x00hello world") == "hello world"
    assert _sanitize_nul("hello world\x00") == "hello world"
    assert _sanitize_nul("hello\x00\x00world") == "helloworld"
    assert _sanitize_nul("\x00") == ""

    # Empty string
    assert _sanitize_nul("") == ""

    # None value
    assert _sanitize_nul(None) == ""

    # Non-string types (should be cast to string representations without NUL)
    assert _sanitize_nul(123) == "123"
    assert _sanitize_nul(12.3) == "12.3"
    assert _sanitize_nul(True) == "True"


def test_sanitize_display_text():
    from services.email_parser import _sanitize_display_text

    # Normal string
    assert _sanitize_display_text("hello world") == "hello world"

    # Strings with NUL characters
    assert _sanitize_display_text("hello\x00world") == "helloworld"

    # Strings with HTML tags
    assert _sanitize_display_text("<b>hello</b> world") == "hello world"
    assert _sanitize_display_text("<script>alert('xss')</script>") == ""
    assert (
        _sanitize_display_text("hello <img src=x onerror=alert(1)>world")
        == "hello world"
    )

    # Strings combining NUL and HTML
    assert _sanitize_display_text("<b>hello\x00</b>") == "hello"
    assert _sanitize_display_text("<script\x00>alert('xss')</script>") == ""
    # Let's see what happens exactly - _sanitize_nul strips NUL first, then strip_html_markup acts on the rest.
    # So "<script\x00>..." becomes "<script>..." and then strip_html_markup strips it.
    assert _sanitize_display_text("<script\x00>alert('xss\x00')</script>") == ""

    # Empty string
    assert _sanitize_display_text("") == ""

    # None value (falls back to _sanitize_nul which converts None to "")
    assert _sanitize_display_text(None) == ""


def _eml_with(headers: str) -> bytes:
    """Build minimal EML bytes with the given header block and a plain body."""
    return (headers.strip() + "\n\nBody text.").encode("utf-8")


def test_parse_eml_marks_valid_date_as_parsed_with_original_header_date():
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
    # The effective (storage) date equals the genuine header date, not a fallback.
    assert parsed["date"] == expected


def test_parse_eml_marks_missing_date_without_promoting_the_fallback():
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <missing-date@test.com>
From: sender@test.com
To: recipient@test.com
Subject: No date header"""
        )
    )

    assert parsed["date_provenance"] == "missing"
    # No original sender date exists; only a collection-time fallback is stored.
    assert parsed["header_date"] is None
    assert parsed["date"].tzinfo is not None


def test_parse_eml_marks_invalid_date_without_promoting_the_fallback():
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


def test_parse_eml_marks_whitespace_only_date_as_missing():
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <whitespace-date@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Whitespace-only date
Date:    """
        )
    )

    # A Date header that is only whitespace carries no sender metadata, so it is
    # treated as missing (not invalid) and the fallback is not promoted.
    assert parsed["date_provenance"] == "missing"
    assert parsed["header_date"] is None
    assert parsed["date"].tzinfo is not None


def test_parse_eml_normalizes_minus_zero_zone_to_utc():
    parsed = parse_eml_bytes(
        _eml_with(
            """Message-ID: <minus-zero-zone@test.com>
From: sender@test.com
To: recipient@test.com
Subject: Minus-zero timezone
Date: Sun, 01 Jan 2023 12:00:00 -0000"""
        )
    )

    # RFC 5322 "-0000" ("no timezone info") makes parsedate_to_datetime return a
    # naive datetime; the parser must normalize it to UTC so the documented
    # timezone-aware contract holds for every parsed header.
    assert parsed["date_provenance"] == "parsed"
    assert parsed["header_date"] is not None
    assert parsed["header_date"].tzinfo is not None
    assert parsed["header_date"].utcoffset() == datetime.timedelta(0)
    assert parsed["date"].tzinfo is not None


def test_parse_eml_marks_embedded_message_id_provenance():
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


def test_parse_eml_marks_missing_message_id_provenance():
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
