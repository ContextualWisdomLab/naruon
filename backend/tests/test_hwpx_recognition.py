"""Executable contracts for safe HWPX section-text recognition."""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from services import hwpx_recognition as recognition


_OPF_NS = "http://www.idpf.org/2007/opf/"
_HP_NS = "http://www.owpml.org/owpml/2021/paragraph"
_HS_NS = "http://www.owpml.org/owpml/2021/section"


def _section_xml(*paragraphs: str) -> str:
    """Return a minimal standards-shaped HWPX section XML document."""
    rendered = "".join(
        f'<hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p>'
        for text in paragraphs
    )
    return (
        f'<hs:sec xmlns:hs="{_HS_NS}" xmlns:hp="{_HP_NS}">'
        f"{rendered}</hs:sec>"
    )


def _content_hpf(
    *,
    manifest: tuple[tuple[str, str], ...],
    spine: tuple[str, ...],
) -> str:
    """Return a minimal OPF manifest/spine used by an HWPX package."""
    manifest_xml = "".join(
        f'<opf:item id="{item_id}" href="{href}" media-type="application/xml"/>'
        for item_id, href in manifest
    )
    spine_xml = "".join(f'<opf:itemref idref="{item_id}"/>' for item_id in spine)
    return (
        f'<opf:package xmlns:opf="{_OPF_NS}"><opf:manifest>{manifest_xml}'
        f"</opf:manifest><opf:spine>{spine_xml}</opf:spine></opf:package>"
    )


def _hwpx_package(
    *,
    sections: dict[str, str],
    spine: tuple[str, ...],
    manifest_hrefs: dict[str, str] | None = None,
    include_version: bool = True,
) -> bytes:
    """Build a small HWPX package with explicit manifest and spine order."""
    hrefs = manifest_hrefs or {
        section_id: f"Contents/{section_id}.xml" for section_id in sections
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"application/hwp+zip")
        if include_version:
            archive.writestr("version.xml", b'<version app="Naruon" />')
        archive.writestr(
            "Contents/content.hpf",
            _content_hpf(
                manifest=tuple((section_id, hrefs[section_id]) for section_id in sections),
                spine=spine,
            ),
        )
        for section_id, xml in sections.items():
            archive.writestr(f"Contents/{section_id}.xml", xml)
    return buffer.getvalue()


def test_recognize_hwpx_follows_spine_and_preserves_paragraph_provenance() -> None:
    """Read sections in OPF spine order and retain semantic source positions."""
    payload = _hwpx_package(
        sections={
            "section0": _section_xml("첫 번째 구역", "둘째 문단"),
            "section1": _section_xml("두 번째 구역"),
        },
        spine=("section1", "section0"),
    )

    records = recognition.recognize_hwpx_package(
        payload,
        filename="proposal.hwpx",
        source_kind="attachment",
        source_record_uid="attachment-42",
    )

    assert records.parse_text == "두 번째 구역\n\n첫 번째 구역\n\n둘째 문단"
    assert records.parse_result.source_content_hash == hashlib.sha256(payload).hexdigest()
    assert [segment.safe_text_content for segment in records.parse_result.segments] == [
        "두 번째 구역",
        "첫 번째 구역",
        "둘째 문단",
    ]
    assert [segment.segment_path for segment in records.parse_result.segments] == [
        "/document[1]/section[1]/paragraph[1]",
        "/document[1]/section[2]/paragraph[1]",
        "/document[1]/section[2]/paragraph[2]",
    ]

    changed_records = recognition.recognize_hwpx_package(
        _hwpx_package(
            sections={"section0": _section_xml("변경된 문서")},
            spine=("section0",),
        ),
        filename="proposal.hwpx",
        source_kind="attachment",
        source_record_uid="attachment-42",
    )
    assert changed_records.parse_result.nodes[0].content_node_uid != (
        records.parse_result.nodes[0].content_node_uid
    )
    assert changed_records.parse_result.segments[0].content_segment_uid != (
        records.parse_result.segments[0].content_segment_uid
    )


def test_recognize_hwpx_rejects_missing_version_member() -> None:
    """Revalidate the required version member before section recognition."""
    payload = _hwpx_package(
        sections={"section0": _section_xml("safe")},
        spine=("section0",),
        include_version=False,
    )

    with pytest.raises(ValueError, match="missing required identity"):
        recognition.recognize_hwpx_package(
            payload,
            filename="missing-version.hwpx",
            source_kind="attachment",
            source_record_uid="attachment-47",
        )


@pytest.mark.parametrize("member_name", ("mimetype", "Contents/content.hpf"))
def test_recognize_hwpx_normalizes_zip_read_failures(
    monkeypatch: pytest.MonkeyPatch,
    member_name: str,
) -> None:
    """Convert ZIP read implementation failures into bounded parse errors."""
    payload = _hwpx_package(
        sections={"section0": _section_xml("safe")},
        spine=("section0",),
    )
    original_read = zipfile.ZipFile.read

    def broken_read(archive, member, *args, **kwargs):
        if getattr(member, "filename", member) == member_name:
            raise zipfile.BadZipFile("simulated read failure")
        return original_read(archive, member, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", broken_read)

    with pytest.raises(ValueError, match="could not be read"):
        recognition.recognize_hwpx_package(
            payload,
            filename="read-failure.hwpx",
            source_kind="attachment",
            source_record_uid="attachment-48",
        )


def test_paragraph_text_does_not_duplicate_nested_paragraphs() -> None:
    """Nested paragraph nodes are skipped by the containing paragraph."""
    nested_section = (
        f'<hs:sec xmlns:hs="{_HS_NS}" xmlns:hp="{_HP_NS}">'
        "<hp:p><hp:p><hp:run><hp:t>nested</hp:t></hp:run></hp:p></hp:p>"
        "</hs:sec>"
    )
    payload = _hwpx_package(
        sections={"section0": nested_section},
        spine=("section0",),
    )

    records = recognition.recognize_hwpx_package(
        payload,
        filename="nested.hwpx",
        source_kind="attachment",
        source_record_uid="attachment-49",
    )

    assert records.parse_text == "nested"
    assert records.paragraph_count == 1


def test_recognize_hwpx_rejects_manifest_path_traversal() -> None:
    """Never resolve an OPF manifest href outside the HWPX package root."""
    payload = _hwpx_package(
        sections={"section0": _section_xml("safe")},
        spine=("section0",),
        manifest_hrefs={"section0": "../section0.xml"},
    )

    with pytest.raises(ValueError, match="unsafe manifest href"):
        recognition.recognize_hwpx_package(
            payload,
            filename="unsafe.hwpx",
            source_kind="attachment",
            source_record_uid="attachment-43",
        )


def test_recognize_hwpx_bounds_expanded_xml_before_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a ZIP expansion budget violation before XML parsing."""
    payload = _hwpx_package(
        sections={"section0": _section_xml("x" * 256)},
        spine=("section0",),
    )
    monkeypatch.setattr(recognition, "MAX_HWPX_XML_MEMBER_BYTES", 64)

    with pytest.raises(ValueError, match="XML member exceeds"):
        recognition.recognize_hwpx_package(
            payload,
            filename="oversized.hwpx",
            source_kind="attachment",
            source_record_uid="attachment-44",
        )


def test_recognize_hwpx_rejects_unsafe_xml_entities() -> None:
    """Defused XML parsing must reject entity-bearing section payloads."""
    dangerous_section = (
        '<!DOCTYPE hs:sec [<!ENTITY exfil SYSTEM "file:///etc/passwd">]>'
        f'<hs:sec xmlns:hs="{_HS_NS}" xmlns:hp="{_HP_NS}">'
        "<hp:p><hp:run><hp:t>&exfil;</hp:t></hp:run></hp:p></hs:sec>"
    )
    payload = _hwpx_package(
        sections={"section0": dangerous_section},
        spine=("section0",),
    )

    with pytest.raises(ValueError, match="unsafe XML"):
        recognition.recognize_hwpx_package(
            payload,
            filename="entity.hwpx",
            source_kind="attachment",
            source_record_uid="attachment-45",
        )


def test_recognize_hwpx_requires_spine_referenced_section() -> None:
    """Fail closed when OPF spine metadata cannot resolve a section member."""
    payload = _hwpx_package(
        sections={"section0": _section_xml("safe")},
        spine=("missing-section",),
    )

    with pytest.raises(ValueError, match="spine item"):
        recognition.recognize_hwpx_package(
            payload,
            filename="missing.hwpx",
            source_kind="attachment",
            source_record_uid="attachment-46",
        )
