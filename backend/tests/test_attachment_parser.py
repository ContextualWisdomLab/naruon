from services.attachment_parser import parse_email_attachment


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
    assert result.parse_status == "parsed"


def test_unsupported_binary_attachment_is_visible_without_raw_bytes():
    result = parse_email_attachment(
        filename="contract.pdf",
        content_type="application/pdf",
        raw_content=b"%PDF-1.7 raw bytes",
    )

    assert result.filename == "contract.pdf"
    assert result.content_type == "application/pdf"
    assert result.content == ""
    assert result.parse_content == ""
    assert result.parse_content_type == "application/pdf"
    assert result.parse_status == "unsupported_content_type"
    assert result.parse_error_code == "unsupported_content_type"
