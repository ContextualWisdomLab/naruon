"""Regression contracts for MIME attachment filename identity."""

from services.attachment_parser import _safe_filename, parse_email_attachment


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


def test_html_markup_filename_cannot_smuggle_generic_mime_extension() -> None:
    """Markup-looking filename text fails closed instead of selecting a parser."""
    result = parse_email_attachment(
        filename="<b>quarterly</b>.json",
        content_type="application/octet-stream",
        raw_content=b'{"project":"Launch"}',
    )

    assert result.filename == "attachment"
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


def test_benign_ampersand_filename_remains_literal() -> None:
    """Ordinary filename punctuation remains unchanged."""
    assert _safe_filename("quarterly report & notes.pdf") == (
        "quarterly report & notes.pdf"
    )
