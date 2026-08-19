"""Safely recognize HWPX section text into Naruon's content graph.

The importer retains HWPX bytes for deferred processing. This module performs the
next deterministic worker-side boundary: it revalidates the ZIP package,
follows the OPF spine order from ``Contents/content.hpf``, parses section XML
with defused XML semantics, and emits paragraph-level provenance without
extracting files, executing active content, or fetching external resources.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

from services.content_graph import ParseResult, PdfDomSection, parse_pdf_dom

HWPX_PARSE_CONTENT_TYPE = "application/hwp+zip"
HWPX_PARSED_STATUS = "hwpx_xml_package_parsed"
HWPX_FAILED_STATUS = "hwpx_xml_package_failed"
MAX_HWPX_XML_MEMBER_BYTES = 4 * 1024 * 1024
MAX_HWPX_TOTAL_XML_BYTES = 16 * 1024 * 1024
MAX_HWPX_PACKAGE_ENTRIES = 4_096
MAX_HWPX_MEMBER_NAME_BYTES = 1 * 1024 * 1024

_HWPX_MIMETYPE = b"application/hwp+zip"
_CONTENT_HPF_PATH = "Contents/content.hpf"
_SECTION_PATH_RE = re.compile(r"^Contents/section[0-9]+\.xml$")


@dataclass(frozen=True, slots=True)
class HwpxRecognitionRecords:
    """Carry recognized HWPX text, graph records, and bounded parse counts."""

    parse_text: str
    parse_result: ParseResult
    section_count: int
    paragraph_count: int


def _local_name(tag: str) -> str:
    """Return the local XML name without trusting a particular namespace URI."""

    return tag.rsplit("}", 1)[-1]


def _safe_member_name(name: str) -> str:
    """Validate a ZIP member as one normalized package-internal POSIX path."""

    if not name or "\\" in name or "\x00" in name:
        raise ValueError("HWPX package contains an unsafe member path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("HWPX package contains an unsafe member path")
    return path.as_posix()


def _package_entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Return unique, unencrypted HWPX members within metadata budgets."""

    entries = archive.infolist()
    if not 0 < len(entries) <= MAX_HWPX_PACKAGE_ENTRIES:
        raise ValueError("HWPX package exceeds the member-count limit")

    result: dict[str, zipfile.ZipInfo] = {}
    aggregate_name_bytes = 0
    for entry in entries:
        name = _safe_member_name(entry.filename)
        aggregate_name_bytes += len(name.encode("utf-8", errors="surrogatepass"))
        if aggregate_name_bytes > MAX_HWPX_MEMBER_NAME_BYTES:
            raise ValueError("HWPX package exceeds the member-name metadata limit")
        if name in result:
            raise ValueError("HWPX package contains duplicate member paths")
        if entry.flag_bits & 0x1:
            raise ValueError("HWPX package contains encrypted members")
        result[name] = entry
    return result


def _read_member(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
    *,
    label: str,
    max_bytes: int = MAX_HWPX_XML_MEMBER_BYTES,
) -> bytes:
    """Read one already-selected XML member within its expansion budget."""

    if entry.is_dir() or entry.file_size > max_bytes:
        raise ValueError(f"HWPX {label} XML member exceeds the expansion limit")
    try:
        payload = archive.read(entry)
    except (NotImplementedError, zipfile.BadZipFile) as exc:
        raise ValueError(f"HWPX {label} XML member could not be read") from exc
    if len(payload) != entry.file_size or len(payload) > max_bytes:
        raise ValueError(f"HWPX {label} XML member exceeds the expansion limit")
    return payload


def _parse_xml(payload: bytes, *, label: str):
    """Parse one bounded XML member with entity/DTD defenses enabled."""

    try:
        return DefusedElementTree.fromstring(payload)
    except (DefusedXmlException, ParseError, ValueError) as exc:
        raise ValueError(f"HWPX {label} contains unsafe XML") from exc


def _resolve_manifest_href(href: str) -> str:
    """Resolve an OPF item href only to the standard HWPX section namespace."""

    value = href.strip()
    if not value or "\\" in value or "\x00" in value or "?" in value or "#" in value:
        raise ValueError("HWPX content.hpf contains an unsafe manifest href")
    raw_path = PurePosixPath(value)
    if raw_path.is_absolute() or any(part in {"", ".", ".."} for part in raw_path.parts):
        raise ValueError("HWPX content.hpf contains an unsafe manifest href")

    if raw_path.parts and raw_path.parts[0] == "Contents":
        resolved = raw_path.as_posix()
    else:
        resolved = (PurePosixPath("Contents") / raw_path).as_posix()
    if not _SECTION_PATH_RE.fullmatch(resolved):
        raise ValueError("HWPX content.hpf contains a non-section spine target")
    return resolved


def _section_paths_from_spine(content_hpf_root) -> tuple[str, ...]:
    """Resolve section member paths using OPF manifest identity and spine order."""

    manifest_element = next(
        (child for child in content_hpf_root if _local_name(child.tag) == "manifest"),
        None,
    )
    spine_element = next(
        (child for child in content_hpf_root if _local_name(child.tag) == "spine"),
        None,
    )
    if manifest_element is None or spine_element is None:
        raise ValueError("HWPX content.hpf is missing manifest or spine metadata")

    manifest: dict[str, str] = {}
    for item in manifest_element:
        if _local_name(item.tag) != "item":
            continue
        item_id = (item.get("id") or "").strip()
        href = (item.get("href") or "").strip()
        if not item_id or not href or item_id in manifest:
            raise ValueError("HWPX content.hpf contains ambiguous manifest identity")
        manifest[item_id] = href

    section_paths: list[str] = []
    for itemref in spine_element:
        if _local_name(itemref.tag) != "itemref":
            continue
        item_id = (itemref.get("idref") or "").strip()
        if not item_id or item_id not in manifest:
            raise ValueError("HWPX spine item cannot be resolved through the manifest")
        section_paths.append(_resolve_manifest_href(manifest[item_id]))

    if not section_paths or len(section_paths) != len(set(section_paths)):
        raise ValueError("HWPX spine must reference unique section members")
    return tuple(section_paths)


def _paragraph_text(paragraph) -> str:
    """Extract text controls from one paragraph without duplicating nested paragraphs."""

    parts: list[str] = []

    def visit(element) -> None:
        for child in element:
            local_name = _local_name(child.tag)
            if local_name == "p":
                continue
            if local_name == "t":
                parts.append("".join(child.itertext()))
            elif local_name in {"lineBreak", "br"}:
                parts.append("\n")
            elif local_name == "tab":
                parts.append("\t")
            else:
                visit(child)

    visit(paragraph)
    return "".join(parts).strip()


def _section_paragraphs(section_root) -> tuple[str, ...]:
    """Return non-empty paragraphs in document order from one HWPX section."""

    paragraphs: list[str] = []
    for element in section_root.iter():
        if _local_name(element.tag) != "p":
            continue
        text = _paragraph_text(element)
        if text:
            paragraphs.append(text)
    return tuple(paragraphs)


def recognize_hwpx_package(
    payload: bytes,
    *,
    filename: str,
    source_kind: str,
    source_record_uid: str,
) -> HwpxRecognitionRecords:
    """Recognize bounded HWPX section text and paragraph provenance.

    ``Contents/content.hpf`` is the ordering authority: manifest IDs resolve
    package paths and spine references define reading order. Each selected XML
    member is bounded before decompression and parsed with ``defusedxml``.
    Images, OLE objects, external resources, macros, and non-section package
    members are intentionally not interpreted by this slice.
    """

    if not isinstance(payload, bytes) or not payload.startswith(b"PK"):
        raise ValueError("Pending attachment payload is not a HWPX package")

    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, ValueError) as exc:
        raise ValueError("Pending attachment payload is not a HWPX package") from exc

    with archive:
        entries = _package_entries(archive)
        mimetype_entry = entries.get("mimetype")
        version_entry = entries.get("version.xml")
        content_hpf_entry = entries.get(_CONTENT_HPF_PATH)
        if (
            mimetype_entry is None
            or version_entry is None
            or content_hpf_entry is None
        ):
            raise ValueError("HWPX package is missing required identity metadata")
        mimetype_payload = _read_member(
            archive,
            mimetype_entry,
            label="mimetype",
            max_bytes=128,
        )
        if mimetype_payload != _HWPX_MIMETYPE:
            raise ValueError("HWPX package has an invalid mimetype member")

        content_hpf_payload = _read_member(
            archive,
            content_hpf_entry,
            label="content.hpf",
        )
        content_hpf_root = _parse_xml(content_hpf_payload, label="content.hpf")
        section_paths = _section_paths_from_spine(content_hpf_root)

        selected_entries: list[zipfile.ZipInfo] = []
        expanded_total = len(content_hpf_payload)
        for section_path in section_paths:
            entry = entries.get(section_path)
            if entry is None:
                raise ValueError("HWPX spine section member is missing from the package")
            if entry.file_size > MAX_HWPX_XML_MEMBER_BYTES:
                raise ValueError("HWPX section XML member exceeds the expansion limit")
            expanded_total += entry.file_size
            if expanded_total > MAX_HWPX_TOTAL_XML_BYTES:
                raise ValueError("HWPX selected XML exceeds the total expansion limit")
            selected_entries.append(entry)

        sections: list[PdfDomSection] = []
        paragraph_count = 0
        for entry in selected_entries:
            section_payload = _read_member(archive, entry, label="section")
            section_root = _parse_xml(section_payload, label="section")
            paragraphs = _section_paragraphs(section_root)
            paragraph_count += len(paragraphs)
            sections.append(PdfDomSection(heading="", paragraphs=paragraphs))

    source_content_hash = hashlib.sha256(payload).hexdigest()
    parse_result = parse_pdf_dom(
        source_kind=source_kind,
        source_record_uid=source_record_uid,
        sections=sections,
        source_content_hash=source_content_hash,
        display_name=filename,
        content_type=HWPX_PARSE_CONTENT_TYPE,
    )
    parse_text = "\n\n".join(
        segment.safe_text_content
        for segment in parse_result.segments
        if segment.segment_kind == "paragraph"
    )
    return HwpxRecognitionRecords(
        parse_text=parse_text,
        parse_result=parse_result,
        section_count=len(sections),
        paragraph_count=paragraph_count,
    )
