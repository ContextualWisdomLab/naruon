"""Regression contracts for MIME attachment filename identity."""

from services.attachment_parser import _safe_filename, parse_email_attachment
from services.email_parser import parse_eml_bytes


def test_html_entity_dot_does_not_change_generic_mime_parser() -> None:
    """HTML entity syntax is literal MIME filename text, not an extension codec."""
    result = parse_email_attachment(
        filename="quarterly&#46;json",
        content_type="application/octet-stream",
        raw_content=b'{"project":"Launch"}',
    )

    assert result.filename == "quarterly&#46;json"
    assert result.parse_content_type == "application/octet-stream"
    assert result.parser_key == "unsupported_binary"
    assert result.parse_status == "unsupported_content_type"


def test_html_display_sanitization_cannot_smuggle_generic_mime_extension() -> None:
    """Safe display projection must not become parser-selection authority."""
    result = parse_email_attachment(
        filename="<b>quarterly</b>.json",
        content_type="application/octet-stream",
        raw_content=b'{"project":"Launch"}',
    )

    assert result.filename == "quarterly.json"
    assert result.parse_content_type == "application/octet-stream"
    assert result.parser_key == "unsupported_binary"
    assert result.parse_status == "unsupported_content_type"


def test_unknown_angle_bracket_filename_cannot_select_generic_parser() -> None:
    """Unknown tag-shaped filename text must not become extension authority."""
    result = parse_email_attachment(
        filename="<Q4>.json",
        content_type="application/octet-stream",
        raw_content=b'{"project":"Launch"}',
    )

    assert result.filename == "attachment"
    assert result.parse_content_type == "application/octet-stream"
    assert result.parser_key == "unsupported_binary"
    assert result.parse_status == "unsupported_content_type"


def test_nul_filename_cannot_create_generic_mime_extension_authority() -> None:
    """A production EML NUL must not disappear into a parser-recognized suffix."""
    parsed = parse_eml_bytes(
        b"Message-ID: <nul-filename@test.com>\r\n"
        b"From: sender@test.com\r\n"
        b"To: recipient@test.com\r\n"
        b"Subject: NUL filename\r\n"
        b"Date: Mon, 27 Apr 2026 10:00:00 +0000\r\n"
        b'Content-Type: multipart/mixed; boundary="mixed-boundary"\r\n'
        b"\r\n"
        b"--mixed-boundary\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"See attached.\r\n"
        b"--mixed-boundary\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b'Content-Disposition: attachment; filename="quarterly.json\x00"\r\n'
        b"\r\n"
        b'{"project":"Launch"}\r\n'
        b"--mixed-boundary--\r\n"
    )

    attachment = parsed["attachments"][0]
    assert attachment["filename"] == "attachment"
    assert attachment["parse_content_type"] == "application/octet-stream"
    assert attachment["parser_key"] == "unsupported_binary"
    assert attachment["parse_status"] == "unsupported_content_type"


def test_rfc2231_control_character_filename_fails_closed() -> None:
    """RFC 2231 decoding must not turn control-bearing names into parser authority."""
    parsed = parse_eml_bytes(
        b"Message-ID: <control-filename@test.com>\r\n"
        b"From: sender@test.com\r\n"
        b"To: recipient@test.com\r\n"
        b"Subject: Control filename\r\n"
        b"Date: Mon, 27 Apr 2026 10:00:00 +0000\r\n"
        b'Content-Type: multipart/mixed; boundary="mixed-boundary"\r\n'
        b"\r\n"
        b"--mixed-boundary\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"See attached.\r\n"
        b"--mixed-boundary\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Disposition: attachment; "
        b"filename*=utf-8''quarterly%0A.json\r\n"
        b"\r\n"
        b'{"project":"Launch"}\r\n'
        b"--mixed-boundary--\r\n"
    )

    attachment = parsed["attachments"][0]
    assert attachment["filename"] == "attachment"
    assert attachment["parse_content_type"] == "application/octet-stream"
    assert attachment["parser_key"] == "unsupported_binary"
    assert attachment["parse_status"] == "unsupported_content_type"


def test_filename_controls_fail_closed_before_display_or_parser_selection() -> None:
    """C0/C1 controls are not valid display or parser-authority characters."""
    for control in ("\t", "\x1b", "\x7f", "\x85"):
        filename = f"quarterly{control}.json"
        result = parse_email_attachment(
            filename=filename,
            content_type="application/octet-stream",
            raw_content=b'{"project":"Launch"}',
        )

        assert _safe_filename(filename) == "attachment"
        assert result.filename == "attachment"
        assert result.parse_content_type == "application/octet-stream"
        assert result.parser_key == "unsupported_binary"
        assert result.parse_status == "unsupported_content_type"


def test_benign_ampersand_filename_remains_literal() -> None:
    """Ordinary filename punctuation remains unchanged."""
    assert _safe_filename("quarterly report & notes.pdf") == (
        "quarterly report & notes.pdf"
    )
