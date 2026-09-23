"""Safely extract bounded text and graph records from an HWPX package."""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass

from defusedxml import ElementTree
from services.content_graph import ParseResult, PdfDomSection, parse_pdf_dom

HWPX_CONTENT_TYPE = "application/hwp+zip"
MAX_HWPX_SECTION_XML_BYTES = 8 * 1024 * 1024
MAX_HWPX_TOTAL_XML_BYTES = 32 * 1024 * 1024
MAX_HWPX_TEXT_CHARS = 1_000_000
_SECTION_NAME_PATTERN = re.compile(r"Contents/section[0-9]+\.xml\Z")
_FORBIDDEN_XML_DECLARATION = re.compile(
    br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE
)


class HwpxRecognitionError(ValueError):
    """Raised when an HWPX package cannot be extracted within safe bounds."""


@dataclass(frozen=True)
class HwpxRecognitionRecords:
    """Carry HWPX text and stable content-graph records."""

    parse_text: str
    source_content_hash: str
    parse_result: ParseResult


def recognize_hwpx(
    *,
    hwpx_bytes: bytes,
    source_record_uid: str,
    display_name: str = "",
) -> HwpxRecognitionRecords:
    """Extract text from bounded HWPX section XML without executing content.

    Only canonical ``Contents/sectionN.xml`` members are read. Encrypted or
    unsupported compression members, XML entity declarations, oversized
    members, and empty documents fail closed before graph records are created.
    """
    sections: list[PdfDomSection] = []
    total_xml_bytes = 0
    try:
        with zipfile.ZipFile(io.BytesIO(hwpx_bytes)) as archive:
            section_infos = sorted(
                (
                    info
                    for info in archive.infolist()
                    if _SECTION_NAME_PATTERN.fullmatch(info.filename)
                ),
                key=lambda info: int(
                    info.filename.removeprefix("Contents/section").removesuffix(
                        ".xml"
                    )
                ),
            )
            if not section_infos:
                raise HwpxRecognitionError("HWPX package has no section XML")
            if len({info.filename for info in section_infos}) != len(section_infos):
                raise HwpxRecognitionError("HWPX package has duplicate sections")

            for info in section_infos:
                if info.flag_bits & 0x1 or info.compress_type not in (
                    zipfile.ZIP_STORED,
                    zipfile.ZIP_DEFLATED,
                ):
                    raise HwpxRecognitionError("HWPX section compression is not allowed")
                if info.file_size > MAX_HWPX_SECTION_XML_BYTES:
                    raise HwpxRecognitionError("HWPX section exceeds the XML size limit")
                total_xml_bytes += info.file_size
                if total_xml_bytes > MAX_HWPX_TOTAL_XML_BYTES:
                    raise HwpxRecognitionError("HWPX XML exceeds the total size limit")
                xml_bytes = archive.read(info)
                if len(xml_bytes) != info.file_size:
                    raise HwpxRecognitionError("HWPX section size changed while reading")
                sections.extend(_parse_section_xml(xml_bytes))
    except HwpxRecognitionError:
        raise
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
    ) as exc:
        raise HwpxRecognitionError("HWPX package could not be safely read") from exc

    paragraphs = tuple(
        paragraph
        for section in sections
        for paragraph in section.paragraphs
        if paragraph.strip()
    )
    parse_text = "\n\n".join(paragraphs)
    if not parse_text.strip():
        raise HwpxRecognitionError("HWPX package contains no readable text")
    if len(parse_text) > MAX_HWPX_TEXT_CHARS:
        raise HwpxRecognitionError("HWPX text exceeds the parse size limit")

    source_content_hash = hashlib.sha256(hwpx_bytes).hexdigest()
    parse_result = parse_pdf_dom(
        source_kind="attachment",
        source_record_uid=source_record_uid,
        sections=sections,
        source_content_hash=source_content_hash,
        display_name=display_name,
        content_type=HWPX_CONTENT_TYPE,
    )
    return HwpxRecognitionRecords(
        parse_text=parse_text,
        source_content_hash=source_content_hash,
        parse_result=parse_result,
    )


def _parse_section_xml(xml_bytes: bytes) -> list[PdfDomSection]:
    """Parse one section into paragraph units without resolving declarations."""
    if _FORBIDDEN_XML_DECLARATION.search(xml_bytes):
        raise HwpxRecognitionError("HWPX XML declarations are not allowed")
    root = ElementTree.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for element in root.iter():
        if _local_name(element.tag) != "p":
            continue
        text = "".join(
            node.text or ""
            for node in element.iter()
            if _local_name(node.tag) == "t"
        )
        normalized = " ".join(text.split())
        if normalized:
            paragraphs.append(normalized)
    if not paragraphs:
        return []
    return [PdfDomSection(heading="", paragraphs=tuple(paragraphs))]


def _local_name(tag: str) -> str:
    """Return an XML local name while rejecting non-element tags."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", maxsplit=1)[-1]
