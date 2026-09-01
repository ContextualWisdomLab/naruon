"""Regression tests for literal percent escapes in decoded MIME filenames.

`email.message.Message.get_filename()` already returns the parsed MIME filename
value. Attachment sanitization must therefore treat ordinary percent escapes as
literal display characters instead of applying URL decoding a second time.
"""

from services.attachment_parser import _safe_filename, parse_email_attachment


def test_safe_filename_preserves_literal_percent_escape_text() -> None:
    """A normal MIME filename containing percent text keeps the sender's name."""
    assert _safe_filename("quarterly%20report.pdf") == "quarterly%20report.pdf"


def test_literal_percent_escape_cannot_invent_parser_extension() -> None:
    """Literal percent text must not manufacture a trusted parser extension."""
    result = parse_email_attachment(
        filename="invoice%2Epdf",
        content_type="application/octet-stream",
        raw_content=b"not a PDF",
    )

    assert result.filename == "invoice%2Epdf"
    assert result.parse_content_type == "application/octet-stream"
    assert result.parser_key == "unsupported_binary"
    assert result.parse_status == "unsupported_content_type"


def test_percent_encoded_path_structure_fails_closed_without_rewriting_name() -> None:
    """Potential downstream path syntax is rejected, not URL-decoded and reused."""
    assert _safe_filename("%2e%2e%2fsecret.txt") == "attachment"
    assert _safe_filename("%252e%252e%252fsecret.txt") == "attachment"
