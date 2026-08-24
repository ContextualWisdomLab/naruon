import base64

import pytest

from services.attachment_parser import (
    MAX_ATTACHMENT_FILENAME_DECODE_ROUNDS,
    MAX_ATTACHMENT_PARSE_SOURCE_BYTES,
    MAX_ATTACHMENT_PARSE_SOURCE_CHARS,
    decode_deferred_attachment_payload,
    get_attachment_parser_manifest,
    parse_email_attachment,
)


def test_html_attachment_preserves_parse_source_and_safe_display_text():
    result = parse_email_attachment(
        filename="<b>report</b>.html",
        content_type="text/html; charset=utf-8",
        raw_content="<h1>Launch</h1><script>alert(1)</script><p>Ship</p>",
    )

    assert result.filename == "report.html"
    assert result.content_type == "text/html"
    assert result.content == "Launch Ship"
    assert result.parse_content == "<h1>Launch</h1><script>alert(1)</script><p>Ship</p>"
    assert result.parse_content_type == "text/html"
    assert result.parse_status == "parsed"
    assert result.parse_error_code is None


@pytest.mark.parametrize(
    ("filename", "expected_filename"),
    [
        ("..\\\\upload.txt", "upload.txt"),
        ("C:\\\\mail\\\\report.pdf", "report.pdf"),
        ("%2e%2e%2fupload.txt", "upload.txt"),
        ("%252e%252e%252fsecret.txt", "secret.txt"),
    ],
)
def test_attachment_filename_normalizes_windows_path_separators(
    filename, expected_filename
):
    """Keep Windows-style attachment paths as safe display basenames."""
    result = parse_email_attachment(
        filename=filename,
        content_type="text/plain",
        raw_content="safe content",
    )

    assert result.filename == expected_filename


def test_attachment_filename_rejects_unresolved_nested_encoding():
    encoded_filename = "%2e%2e%2fsecret.txt"
    for _ in range(MAX_ATTACHMENT_FILENAME_DECODE_ROUNDS):
        encoded_filename = encoded_filename.replace("%", "%25")

    result = parse_email_attachment(
        filename=encoded_filename,
        content_type="text/plain",
        raw_content="safe content",
    )

    assert result.filename == "attachment"


def test_markdown_attachment_is_parseable_markdown():
    result = parse_email_attachment(
        filename="plan.md",
        content_type="text/markdown",
        raw_content="# Plan\n\nShip graph",
    )

    assert result.filename == "plan.md"
    assert result.content == "# Plan Ship graph"
    assert result.parse_content == "# Plan\n\nShip graph"
    assert result.parse_content_type == "text/markdown"
    assert result.parser_key == "markdown"
    assert result.parse_status == "parsed"


def test_parser_manifest_lists_supported_and_unsupported_format_families():
    manifest = get_attachment_parser_manifest()
    parser_keys = {descriptor.parser_key for descriptor in manifest}

    assert {
        "plain_text",
        "html",
        "markdown",
        "json",
        "csv",
        "xml",
        "calendar",
        "pdf",
        "unsupported_binary",
    } <= parser_keys
    markdown_descriptor = next(
        descriptor for descriptor in manifest if descriptor.parser_key == "markdown"
    )
    assert "text/markdown" in markdown_descriptor.content_types
    assert ".md" in markdown_descriptor.extensions
    json_descriptor = next(
        descriptor for descriptor in manifest if descriptor.parser_key == "json"
    )
    assert "application/json" in json_descriptor.content_types
    assert ".json" in json_descriptor.extensions
    calendar_descriptor = next(
        descriptor for descriptor in manifest if descriptor.parser_key == "calendar"
    )
    assert "text/calendar" in calendar_descriptor.content_types
    assert ".ics" in calendar_descriptor.extensions


def test_generic_binary_content_type_can_fall_back_to_markdown_extension():
    result = parse_email_attachment(
        filename="plan.md",
        content_type="application/octet-stream",
        raw_content="# Plan\n\nShip graph",
    )

    assert result.content_type == "application/octet-stream"
    assert result.parse_content_type == "text/markdown"
    assert result.parser_key == "markdown"
    assert result.parse_status == "parsed"
    assert result.content == "# Plan Ship graph"


def test_generic_binary_content_type_can_fall_back_to_json_extension():
    result = parse_email_attachment(
        filename="status.json",
        content_type="application/octet-stream",
        raw_content='{"project": "Launch"}',
    )

    assert result.content_type == "application/octet-stream"
    assert result.parse_content_type == "application/json"
    assert result.parser_key == "json"
    assert result.parse_status == "parsed"
    assert result.content == '{"project": "Launch"}'


def test_structured_non_pdf_attachment_media_types_are_parseable():
    cases = [
        ("status.csv", "text/csv; charset=utf-8", "name,status\nLaunch,Ready", "csv"),
        ("status.xml", "application/xml", "<root>Launch</root>", "xml"),
        (
            "invite.ics",
            "text/calendar",
            "BEGIN:VCALENDAR\nSUMMARY:Launch\nEND:VCALENDAR",
            "calendar",
        ),
    ]

    for filename, content_type, raw_content, parser_key in cases:
        result = parse_email_attachment(
            filename=filename,
            content_type=content_type,
            raw_content=raw_content,
        )

        assert result.filename == filename
        assert result.parser_key == parser_key
        assert result.parse_status == "parsed"
        assert result.parse_error_code is None
        assert result.parse_content == raw_content


def test_oversized_text_attachment_is_metadata_only_without_raw_content():
    result = parse_email_attachment(
        filename="huge.txt",
        content_type="text/plain",
        raw_content="A" * (MAX_ATTACHMENT_PARSE_SOURCE_CHARS + 1),
    )

    assert result.content == ""
    assert result.parse_content == ""
    assert result.parse_content_type == "text/plain"
    assert result.parser_key == "plain_text"
    assert result.parse_status == "parse_size_limit_exceeded"
    assert result.parse_error_code == "parse_size_limit_exceeded"


def test_unsupported_binary_attachment_is_visible_without_raw_bytes():
    result = parse_email_attachment(
        filename="archive.zip",
        content_type="application/zip",
        raw_content=b"PK\x03\x04 raw bytes",
    )

    assert result.filename == "archive.zip"
    assert result.content_type == "application/zip"
    assert result.content == ""
    assert result.parse_content == ""
    assert result.parse_content_type == "application/zip"
    assert result.parser_key == "unsupported_binary"
    assert result.parse_status == "unsupported_content_type"
    assert result.parse_error_code == "unsupported_content_type"


def test_pdf_attachment_is_deferred_pending_newsdom_recognition():
    raw = b"%PDF-1.7 raw bytes"
    result = parse_email_attachment(
        filename="contract.pdf",
        content_type="application/pdf",
        raw_content=raw,
    )

    assert result.filename == "contract.pdf"
    assert result.content_type == "application/pdf"
    # Heavy OCR/MinerU recognition is deferred to the worker: nothing is parsed
    # inline, and the attachment carries the pending status. The raw bytes are
    # retained as a base64 payload so the worker can recognize them later.
    assert result.parse_content == ""
    assert result.parse_content_type == "application/pdf"
    assert result.parser_key == "pdf"
    assert result.parse_status == "pdf_dom_recognition_pending"
    assert result.parse_error_code is None
    assert decode_deferred_attachment_payload(result.content) == raw


def test_pdf_extension_with_generic_content_type_is_deferred_pending():
    result = parse_email_attachment(
        filename="contract.pdf",
        content_type="application/octet-stream",
        raw_content=b"%PDF-1.7 raw bytes",
    )

    assert result.parse_content_type == "application/pdf"
    assert result.parser_key == "pdf"
    assert result.parse_status == "pdf_dom_recognition_pending"


def test_invalid_pdf_payload_is_rejected_before_deferred_recognition():
    result = parse_email_attachment(
        filename="not-a-pdf.pdf",
        content_type="application/pdf",
        raw_content=b"plain text with a PDF content type",
    )

    assert result.content == ""
    assert result.parse_status == "invalid_pdf_payload"
    assert result.parse_error_code == "invalid_pdf_payload"


def test_oversized_pdf_payload_is_not_retained():
    result = parse_email_attachment(
        filename="huge.pdf",
        content_type="application/pdf",
        raw_content=b"%PDF-" + b"A" * MAX_ATTACHMENT_PARSE_SOURCE_BYTES,
    )

    assert result.content == ""
    assert result.parse_status == "parse_size_limit_exceeded"
    assert result.parse_error_code == "parse_size_limit_exceeded"


@pytest.mark.parametrize(
    "raw_content",
    ["plain text", None, 12345],
)
def test_non_binary_pdf_inputs_are_rejected(raw_content):
    result = parse_email_attachment(
        filename="not-a-pdf.pdf",
        content_type="application/pdf",
        raw_content=raw_content,
    )

    assert result.parse_status == "invalid_pdf_payload"
    assert result.parse_error_code == "invalid_pdf_payload"


def test_string_pdf_input_round_trips_as_deferred_bytes():
    result = parse_email_attachment(
        filename="string.pdf",
        content_type="application/pdf",
        raw_content="%PDF-1.7 string fixture",
    )

    assert decode_deferred_attachment_payload(result.content) == (
        b"%PDF-1.7 string fixture"
    )


def test_deferred_pdf_decoder_rejects_non_pdf_and_oversized_payloads(monkeypatch):
    non_pdf = base64.b64encode(b"not a PDF").decode("ascii")
    with pytest.raises(ValueError, match="not a PDF"):
        decode_deferred_attachment_payload(non_pdf)

    monkeypatch.setattr(
        "services.attachment_parser.MAX_ATTACHMENT_PARSE_SOURCE_BYTES", 5
    )
    oversized = base64.b64encode(b"%PDF-1.7").decode("ascii")
    with pytest.raises(ValueError, match="size limit"):
        decode_deferred_attachment_payload(oversized)
