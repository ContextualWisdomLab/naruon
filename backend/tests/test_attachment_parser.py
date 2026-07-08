from services.attachment_parser import (
    MAX_ATTACHMENT_PARSE_SOURCE_CHARS,
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
        "pdf",
        "unsupported_binary",
    } <= parser_keys
    markdown_descriptor = next(
        descriptor for descriptor in manifest if descriptor.parser_key == "markdown"
    )
    assert "text/markdown" in markdown_descriptor.content_types
    assert ".md" in markdown_descriptor.extensions


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
    result = parse_email_attachment(
        filename="contract.pdf",
        content_type="application/pdf",
        raw_content=b"%PDF-1.7 raw bytes",
    )

    assert result.filename == "contract.pdf"
    assert result.content_type == "application/pdf"
    # Heavy OCR/MinerU recognition is deferred to the worker: nothing is parsed
    # inline, and the attachment carries the pending status.
    assert result.content == ""
    assert result.parse_content == ""
    assert result.parse_content_type == "application/pdf"
    assert result.parser_key == "pdf"
    assert result.parse_status == "pdf_dom_recognition_pending"
    assert result.parse_error_code is None


def test_pdf_extension_with_generic_content_type_is_deferred_pending():
    result = parse_email_attachment(
        filename="contract.pdf",
        content_type="application/octet-stream",
        raw_content=b"%PDF-1.7 raw bytes",
    )

    assert result.parse_content_type == "application/pdf"
    assert result.parser_key == "pdf"
    assert result.parse_status == "pdf_dom_recognition_pending"
