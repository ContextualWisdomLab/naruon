import base64
from io import BytesIO
import struct
from zipfile import ZipFile

import pytest

from services.attachment_parser import (
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
        "vcard",
        "nested_email",
        "pdf",
        "image_metadata",
        "office_text",
        "archive_manifest",
        "audio_metadata",
        "legacy_office_metadata",
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
    assert "application/ics" in calendar_descriptor.content_types
    assert ".ics" in calendar_descriptor.extensions


def _zip_fixture(*members: tuple[str, str]) -> bytes:
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        for filename, content in members:
            archive.writestr(filename, content)
    return payload.getvalue()


def _png_fixture(width: int = 320, height: int = 200) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
    )


def _jpeg_fixture(width: int = 640, height: int = 480) -> bytes:
    sof_payload = b"\x08" + struct.pack(">HH", height, width) + b"\x00" * 10
    return b"\xff\xd8\xff\xc0" + struct.pack(">H", len(sof_payload) + 2) + sof_payload


@pytest.mark.parametrize(
    ("filename", "content_type", "raw_content", "format_name"),
    [
        ("preview.png", "image/png", _png_fixture(), "png"),
        ("preview.jpg", "image/jpeg", _jpeg_fixture(), "jpeg"),
        ("preview.gif", "image/gif", b"GIF89a" + struct.pack("<HH", 80, 60), "gif"),
        (
            "preview.bmp",
            "image/bmp",
            b"BM" + bytes(12) + struct.pack("<Iii", 40, 100, 75),
            "bmp",
        ),
    ],
)
def test_image_attachment_metadata_is_searchable_without_pixel_decoding(
    filename, content_type, raw_content, format_name
):
    result = parse_email_attachment(
        filename=filename,
        content_type=content_type,
        raw_content=raw_content,
    )

    assert result.parser_key == "image_metadata"
    assert result.parse_status == "parsed"
    assert result.parse_content_type == "text/plain"
    assert result.parse_content == result.content
    assert f"format={format_name}" in result.content
    assert "width=" in result.content
    assert "height=" in result.content
    assert "animated=no" in result.content


def test_generic_image_mime_uses_filename_extension_for_metadata_parser():
    result = parse_email_attachment(
        filename="preview.png",
        content_type="application/octet-stream",
        raw_content=_png_fixture(12, 34),
    )

    assert result.parser_key == "image_metadata"
    assert result.parse_status == "parsed"
    assert "width=12px" in result.content
    assert "height=34px" in result.content


@pytest.mark.parametrize(
    ("filename", "content_type", "member", "text", "format_name"),
    [
        (
            "plan.docx",
            "application/octet-stream",
            (
                "word/document.xml",
                "<w:document xmlns:w='urn:w'><w:t>Plan</w:t></w:document>",
            ),
            "Plan",
            "docx",
        ),
        (
            "budget.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ("xl/sharedStrings.xml", "<sst xmlns='urn:x'><si><t>Budget</t></si></sst>"),
            "Budget",
            "xlsx",
        ),
        (
            "briefing.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            (
                "ppt/slides/slide1.xml",
                "<p:sld xmlns:p='urn:p' xmlns:a='urn:a'><a:t>Briefing</a:t></p:sld>",
            ),
            "Briefing",
            "pptx",
        ),
        (
            "report.hwpx",
            "application/haansoftdocx",
            (
                "Contents/section0.xml",
                "<hp:sec xmlns:hp='urn:hp'><hp:t>Report</hp:t></hp:sec>",
            ),
            "Report",
            "hwpx",
        ),
    ],
)
def test_office_attachment_text_is_indexed_from_bounded_xml_parts(
    filename, content_type, member, text, format_name
):
    result = parse_email_attachment(
        filename=filename,
        content_type=content_type,
        raw_content=_zip_fixture(member),
    )

    assert result.parser_key == "office_text"
    assert result.parse_status == "parsed"
    assert result.parse_content_type == "text/plain"
    assert f"format={format_name}" in result.content
    assert f"text={text}" in result.content


def test_generic_office_mime_uses_filename_extension_for_text_parser():
    result = parse_email_attachment(
        filename="plan.docx",
        content_type="application/octet-stream",
        raw_content=_zip_fixture(
            (
                "word/document.xml",
                "<w:document xmlns:w='urn:w'><w:t>Plan</w:t></w:document>",
            )
        ),
    )

    assert result.content_type == "application/octet-stream"
    assert result.parse_content_type == "text/plain"
    assert result.parse_status == "parsed"
    assert "text=Plan" in result.content


def test_invalid_office_attachment_fails_closed_without_binary_content():
    result = parse_email_attachment(
        filename="broken.docx",
        content_type="application/octet-stream",
        raw_content=b"not a zip archive",
    )

    assert result.content == ""
    assert result.parse_content == ""
    assert result.parser_key == "office_text"
    assert result.parse_status == "office_text_parse_failed"
    assert result.parse_error_code == "office_text_parse_failed"


def test_zip_attachment_indexes_manifest_without_extracting_members():
    result = parse_email_attachment(
        filename="bundle.zip",
        content_type="application/x-zip-compressed",
        raw_content=_zip_fixture(
            ("docs/plan.txt", "Plan"), ("data/status.csv", "Ready")
        ),
    )

    assert result.parser_key == "archive_manifest"
    assert result.parse_status == "parsed"
    assert result.parse_content_type == "text/plain"
    assert "entries=2" in result.content
    assert "docs/plan.txt" in result.content
    assert "data/status.csv" in result.content


def test_invalid_zip_attachment_fails_closed_without_binary_content():
    result = parse_email_attachment(
        filename="broken.zip",
        content_type="application/zip",
        raw_content=b"not a zip archive",
    )

    assert result.content == ""
    assert result.parse_content == ""
    assert result.parser_key == "archive_manifest"
    assert result.parse_status == "archive_manifest_parse_failed"
    assert result.parse_error_code == "archive_manifest_parse_failed"


def test_nested_email_attachment_indexes_safe_headers_only():
    result = parse_email_attachment(
        filename="forwarded.eml",
        content_type="application/octet-stream",
        raw_content=(
            b"From: sender@example.com\nSubject: Project plan\n"
            b"Content-Type: text/plain\n\nbody"
        ),
    )

    assert result.parser_key == "nested_email"
    assert result.parse_status == "parsed"
    assert result.parse_content_type == "text/plain"
    assert "subject=Project plan" in result.content
    assert "sender=sender@example.com" in result.content


def test_mp3_attachment_indexes_bounded_container_metadata():
    result = parse_email_attachment(
        filename="briefing.mp3",
        content_type="audio/mp3",
        raw_content=b"ID3\x04\x00\x00\x00\x00\x00\x03abc",
    )

    assert result.parser_key == "audio_metadata"
    assert result.parse_status == "parsed"
    assert "format=mp3" in result.content
    assert "id3=yes" in result.content


def test_invalid_mp3_attachment_fails_closed_without_binary_content():
    result = parse_email_attachment(
        filename="broken.mp3",
        content_type="audio/mpeg",
        raw_content=b"not an mp3",
    )

    assert result.content == ""
    assert result.parser_key == "audio_metadata"
    assert result.parse_status == "audio_metadata_parse_failed"
    assert result.parse_error_code == "audio_metadata_parse_failed"


def test_legacy_doc_attachment_indexes_ole_container_metadata():
    result = parse_email_attachment(
        filename="legacy.doc",
        content_type="application/msword",
        raw_content=b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 8,
    )

    assert result.parser_key == "legacy_office_metadata"
    assert result.parse_status == "parsed"
    assert "format=doc" in result.content
    assert "container=ole" in result.content


def test_invalid_legacy_doc_attachment_fails_closed_without_binary_content():
    result = parse_email_attachment(
        filename="broken.doc",
        content_type="application/msword",
        raw_content=b"not an OLE document",
    )

    assert result.content == ""
    assert result.parser_key == "legacy_office_metadata"
    assert result.parse_status == "legacy_office_metadata_parse_failed"
    assert result.parse_error_code == "legacy_office_metadata_parse_failed"


def test_image_signature_wins_when_mail_mime_type_is_wrong():
    result = parse_email_attachment(
        filename="preview.jpg",
        content_type="image/jpeg",
        raw_content=_png_fixture(12, 34),
    )

    assert result.parse_status == "parsed"
    assert "format=png" in result.content
    assert "width=12px" in result.content
    assert "height=34px" in result.content


def test_invalid_image_metadata_fails_closed_without_retaining_binary_content():
    result = parse_email_attachment(
        filename="broken.png",
        content_type="image/png",
        raw_content=b"not an image",
    )

    assert result.content == ""
    assert result.parse_content == ""
    assert result.parser_key == "image_metadata"
    assert result.parse_status == "image_metadata_parse_failed"
    assert result.parse_error_code == "image_metadata_parse_failed"


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
        (
            "invite.ics",
            "application/ics",
            "BEGIN:VCALENDAR\nSUMMARY:Launch\nEND:VCALENDAR",
            "calendar",
        ),
        (
            "contact.vcf",
            "text/x-vcard",
            "BEGIN:VCARD\nFN:Launch Owner\nEND:VCARD",
            "vcard",
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
        filename="unknown.bin",
        content_type="application/octet-stream",
        raw_content=b"PK\x03\x04 raw bytes",
    )

    assert result.filename == "unknown.bin"
    assert result.content_type == "application/octet-stream"
    assert result.content == ""
    assert result.parse_content == ""
    assert result.parse_content_type == "application/octet-stream"
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
