"""Regression tests for bounded HWPX XML extraction."""

import io
import zipfile

import pytest

from services import hwpx_recognition as hwpx_module

HwpxRecognitionError = hwpx_module.HwpxRecognitionError
recognize_hwpx = hwpx_module.recognize_hwpx


def _package(
    section_xml: str,
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    duplicate_section: bool = False,
) -> bytes:
    """Build a package with the same members admitted by attachment parsing."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        archive.writestr("version.xml", "<version/>")
        archive.writestr("Contents/content.hpf", "<package/>")
        archive.writestr("Contents/section0.xml", section_xml, compress_type=compression)
        if duplicate_section:
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr(
                    "Contents/section0.xml",
                    section_xml,
                    compress_type=compression,
                )
    return stream.getvalue()


def test_recognize_hwpx_extracts_paragraphs_and_graph_records() -> None:
    payload = _package(
        "<hp:sec xmlns:hp='urn:hancom:hwpml'>"
        "<hp:p><hp:t>첫 문단</hp:t></hp:p>"
        "<hp:p><hp:t>둘째</hp:t><hp:t> 문단</hp:t></hp:p>"
        "</hp:sec>"
    )

    result = recognize_hwpx(
        hwpx_bytes=payload,
        source_record_uid="attachment-1",
        display_name="policy.hwpx",
    )

    assert result.parse_text == "첫 문단\n\n둘째 문단"
    assert result.parse_result.content_type == "application/hwp+zip"
    assert len(result.parse_result.segments) == 2
    assert result.source_content_hash


def test_recognize_hwpx_rejects_missing_sections() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        archive.writestr("version.xml", "<version/>")
        archive.writestr("Contents/content.hpf", "<package/>")

    with pytest.raises(HwpxRecognitionError, match="no section"):
        recognize_hwpx(hwpx_bytes=stream.getvalue(), source_record_uid="attachment-2")


def test_recognize_hwpx_rejects_duplicate_sections() -> None:
    payload = _package(
        "<sec><p><t>text</t></p></sec>",
        duplicate_section=True,
    )

    with pytest.raises(HwpxRecognitionError, match="duplicate"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-3")


def test_recognize_hwpx_rejects_entity_declarations_and_malformed_xml() -> None:
    entity_payload = _package(
        "<!DOCTYPE sec [<!ENTITY x 'blocked'>]><sec>&x;</sec>"
    )
    with pytest.raises(HwpxRecognitionError, match="declarations"):
        recognize_hwpx(hwpx_bytes=entity_payload, source_record_uid="attachment-4")

    malformed_payload = _package("<sec>")
    with pytest.raises(HwpxRecognitionError, match="safely read"):
        recognize_hwpx(
            hwpx_bytes=malformed_payload,
            source_record_uid="attachment-5",
        )


def test_recognize_hwpx_rejects_unsupported_compression() -> None:
    if not hasattr(zipfile, "ZIP_BZIP2"):
        pytest.skip("Python zipfile has no BZIP2 support")
    payload = _package(
        "<sec><p><t>text</t></p></sec>",
        compression=zipfile.ZIP_BZIP2,
    )

    with pytest.raises(HwpxRecognitionError, match="compression"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-6")


def test_recognize_hwpx_enforces_section_and_total_xml_limits(monkeypatch) -> None:
    payload = _package("<sec><p><t>text</t></p></sec>")
    monkeypatch.setattr(hwpx_module, "MAX_HWPX_SECTION_XML_BYTES", 1)
    with pytest.raises(HwpxRecognitionError, match="section exceeds"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-7")

    monkeypatch.setattr(hwpx_module, "MAX_HWPX_SECTION_XML_BYTES", 10_000)
    monkeypatch.setattr(hwpx_module, "MAX_HWPX_TOTAL_XML_BYTES", 1)
    with pytest.raises(HwpxRecognitionError, match="total size"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-8")


def test_recognize_hwpx_rejects_changed_read_size(monkeypatch) -> None:
    payload = _package("<sec><p><t>text</t></p></sec>")

    monkeypatch.setattr(zipfile.ZipFile, "read", lambda _archive, _info: b"")
    with pytest.raises(HwpxRecognitionError, match="size changed"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-9")


def test_recognize_hwpx_enforces_text_limit(monkeypatch) -> None:
    payload = _package("<sec><p><t>text</t></p></sec>")
    monkeypatch.setattr(hwpx_module, "MAX_HWPX_TEXT_CHARS", 1)

    with pytest.raises(HwpxRecognitionError, match="text exceeds"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-10")


def test_recognize_hwpx_rejects_empty_text_and_non_string_xml_tags() -> None:
    payload = _package("<sec xmlns='urn:example'><p><b /></p></sec>")
    with pytest.raises(HwpxRecognitionError, match="no readable"):
        recognize_hwpx(hwpx_bytes=payload, source_record_uid="attachment-11")

    assert hwpx_module._local_name(None) == ""
