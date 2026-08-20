"""Classify email attachments and retain safe deferred parser inputs."""

import base64
import binascii
import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .text_safety import strip_html_markup

_GENERIC_CONTENT_TYPES = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
    "application/x-binary",
}
_HWPX_CONTENT_TYPES = (
    "application/hwp+zip",
    "application/x-hwp+zip",
    "application/vnd.hancom.hwpx",
)
_HWP_CONTENT_TYPES = (
    "application/x-hwp",
    "application/vnd.hancom.hwp",
    "application/haansofthwp",
)
_HWP_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_HWP_DOCUMENT_SIGNATURE = b"HWP Document File"
_HWPX_MIMETYPE = b"application/hwp+zip"
_ZIP_END_RECORD_SIGNATURE = b"PK\x05\x06"
_ZIP_END_RECORD_SIZE = 22
_ZIP_MAX_COMMENT_BYTES = 65_535
_ZIP_END_RECORD = struct.Struct("<4s4H2LH")
MAX_ATTACHMENT_PARSE_SOURCE_CHARS = 1_000_000
# Keep deferred attachment retention aligned with the email import transport.
MAX_ATTACHMENT_PARSE_SOURCE_BYTES = 64 * 1024 * 1024
MAX_HWPX_ZIP_ENTRIES = 4_096
MAX_HWPX_CENTRAL_DIRECTORY_BYTES = 4 * 1024 * 1024
MAX_HWPX_ZIP_NAME_BYTES = 1 * 1024 * 1024
MAX_HWPX_MIMETYPE_BYTES = 128


@dataclass(frozen=True)
class AttachmentParserDescriptor:
    """Describe one supported attachment parser surface."""

    parser_key: str
    display_name: str
    content_types: tuple[str, ...]
    extensions: tuple[str, ...]
    parse_status: str


_PARSER_MANIFEST = (
    AttachmentParserDescriptor(
        parser_key="plain_text",
        display_name="Plain text attachments",
        content_types=("text/plain",),
        extensions=(".txt", ".text"),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="html",
        display_name="HTML attachments",
        content_types=("text/html",),
        extensions=(".html", ".htm"),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="markdown",
        display_name="Markdown attachments",
        content_types=("text/markdown", "text/x-markdown", "application/markdown"),
        extensions=(".md", ".markdown"),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="json",
        display_name="JSON attachments",
        content_types=("application/json", "text/json"),
        extensions=(".json",),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="csv",
        display_name="CSV attachments",
        content_types=("text/csv", "application/csv"),
        extensions=(".csv",),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="xml",
        display_name="XML attachments",
        content_types=("application/xml", "text/xml"),
        extensions=(".xml",),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="calendar",
        display_name="iCalendar attachments",
        content_types=("text/calendar",),
        extensions=(".ics", ".ifb"),
        parse_status="parsed",
    ),
    AttachmentParserDescriptor(
        parser_key="pdf",
        display_name="PDF documents (NewsDOM recognition)",
        content_types=("application/pdf",),
        extensions=(".pdf",),
        parse_status="pdf_dom_recognition_pending",
    ),
    AttachmentParserDescriptor(
        parser_key="hwpx",
        display_name="HWPX documents (OWPML XML package recognition)",
        content_types=_HWPX_CONTENT_TYPES,
        extensions=(".hwpx", ".owpml"),
        parse_status="hwpx_xml_package_pending",
    ),
    AttachmentParserDescriptor(
        parser_key="hwp",
        display_name="HWP binary documents (sandboxed conversion)",
        content_types=_HWP_CONTENT_TYPES,
        extensions=(".hwp",),
        parse_status="hwp_conversion_pending",
    ),
    AttachmentParserDescriptor(
        parser_key="unsupported_binary",
        display_name="Unsupported binary attachments",
        content_types=("application/octet-stream",),
        extensions=(),
        parse_status="unsupported_content_type",
    ),
)
# Statuses whose recognition is too heavy to run inline during import. The
# attachment is stored with the pending status and a background worker later
# calls a sandboxed recognizer/converter to fill parse_content and content graph.
_DEFERRED_PARSE_STATUSES = frozenset(
    {
        "pdf_dom_recognition_pending",
        "hwpx_xml_package_pending",
        "hwp_conversion_pending",
    }
)
_SUPPORTED_CONTENT_TYPES = {
    content_type
    for descriptor in _PARSER_MANIFEST
    if descriptor.parse_status == "parsed"
    for content_type in descriptor.content_types
}
_DEFERRED_DESCRIPTORS_BY_CONTENT_TYPE = {
    content_type: descriptor
    for descriptor in _PARSER_MANIFEST
    if descriptor.parse_status in _DEFERRED_PARSE_STATUSES
    for content_type in descriptor.content_types
}
_EXTENSION_CONTENT_TYPES = {
    extension: descriptor.content_types[0]
    for descriptor in _PARSER_MANIFEST
    if descriptor.parse_status == "parsed"
    or descriptor.parse_status in _DEFERRED_PARSE_STATUSES
    for extension in descriptor.extensions
}
_DEFERRED_PAYLOAD_ERROR_MESSAGES = {
    "invalid_pdf_payload": "Pending attachment payload is not a PDF",
    "invalid_hwpx_payload": "Pending attachment payload is not a HWPX package",
    "invalid_hwp_payload": "Pending attachment payload is not a HWP binary document",
}


@dataclass(frozen=True)
class AttachmentParseResult:
    """Carry display, parser, and deferred-recognition attachment fields."""

    filename: str
    content: str
    content_type: str
    parse_content: str
    parse_content_type: str
    parser_key: str
    parse_status: str
    parse_error_code: str | None


def get_attachment_parser_manifest() -> list[AttachmentParserDescriptor]:
    """Return a mutable snapshot of the attachment parser manifest."""
    return list(_PARSER_MANIFEST)


def parse_email_attachment(
    *,
    filename: str | None,
    content_type: str | None,
    raw_content: Any,
) -> AttachmentParseResult:
    """Classify and normalize one attachment without running heavy parsers."""
    safe_filename = _safe_filename(filename)
    normalized_content_type = _normalize_content_type(content_type)
    parse_content_type = _parse_content_type_for(
        safe_filename,
        normalized_content_type,
    )

    deferred_descriptor = _DEFERRED_DESCRIPTORS_BY_CONTENT_TYPE.get(parse_content_type)
    if deferred_descriptor is not None:
        # Heavy recognition (OCR/MinerU, HWPX XML section extraction, or HWP
        # binary conversion) must not run inline during import. Retain the raw
        # bytes as a base64 payload in ``content`` so the worker can recognize
        # them later; mark the attachment pending. The pending status gates
        # display, and the worker overwrites ``content`` with recognized text on
        # success. Without this the source bytes are discarded and recognition
        # is impossible.
        deferred_payload = _coerce_deferred_payload_bytes(raw_content)
        if len(deferred_payload) > MAX_ATTACHMENT_PARSE_SOURCE_BYTES:
            return AttachmentParseResult(
                filename=safe_filename,
                content="",
                content_type=normalized_content_type,
                parse_content="",
                parse_content_type=parse_content_type,
                parser_key=deferred_descriptor.parser_key,
                parse_status="parse_size_limit_exceeded",
                parse_error_code="parse_size_limit_exceeded",
            )
        payload_error_code = _deferred_payload_error_code(
            parse_content_type,
            deferred_payload,
        )
        if payload_error_code is not None:
            return AttachmentParseResult(
                filename=safe_filename,
                content="",
                content_type=normalized_content_type,
                parse_content="",
                parse_content_type=parse_content_type,
                parser_key=deferred_descriptor.parser_key,
                parse_status=payload_error_code,
                parse_error_code=payload_error_code,
            )
        return AttachmentParseResult(
            filename=safe_filename,
            content=_encode_deferred_payload(deferred_payload),
            content_type=normalized_content_type,
            parse_content="",
            parse_content_type=parse_content_type,
            parser_key=deferred_descriptor.parser_key,
            parse_status=deferred_descriptor.parse_status,
            parse_error_code=None,
        )

    if parse_content_type not in _SUPPORTED_CONTENT_TYPES:
        parser_key = _parser_key_for(
            parse_content_type,
            "unsupported_content_type",
        )
        return AttachmentParseResult(
            filename=safe_filename,
            content="",
            content_type=normalized_content_type,
            parse_content="",
            parse_content_type=normalized_content_type,
            parser_key=parser_key,
            parse_status="unsupported_content_type",
            parse_error_code="unsupported_content_type",
        )

    parser_key = _parser_key_for(parse_content_type, "parsed")
    parse_content = _coerce_text(raw_content).strip()
    if len(parse_content) > MAX_ATTACHMENT_PARSE_SOURCE_CHARS:
        return AttachmentParseResult(
            filename=safe_filename,
            content="",
            content_type=normalized_content_type,
            parse_content="",
            parse_content_type=parse_content_type,
            parser_key=parser_key,
            parse_status="parse_size_limit_exceeded",
            parse_error_code="parse_size_limit_exceeded",
        )

    return AttachmentParseResult(
        filename=safe_filename,
        content=_display_text(parse_content),
        content_type=normalized_content_type,
        parse_content=parse_content,
        parse_content_type=parse_content_type,
        parser_key=parser_key,
        parse_status="parsed",
        parse_error_code=None,
    )


def _normalize_content_type(content_type: str | None) -> str:
    """Return a lowercase MIME type without parameters."""
    normalized = (content_type or "application/octet-stream").split(";", 1)[0]
    normalized = normalized.strip().lower()
    return normalized or "application/octet-stream"


def _parse_content_type_for(filename: str, content_type: str) -> str:
    """Resolve generic MIME types from a recognized filename extension."""
    if content_type not in _GENERIC_CONTENT_TYPES:
        return content_type
    extension = Path(filename).suffix.lower()
    return _EXTENSION_CONTENT_TYPES.get(extension, content_type)


def _parser_key_for(parse_content_type: str, parse_status: str) -> str:
    """Return the parser key associated with a parse MIME type and status."""
    if parse_status == "unsupported_content_type":
        return "unsupported_binary"
    for descriptor in _PARSER_MANIFEST:
        if parse_content_type in descriptor.content_types:
            return descriptor.parser_key
    return "unsupported_binary"


def _safe_filename(filename: str | None) -> str:
    """Return a basename-only attachment display filename."""
    display_filename = strip_html_markup(_sanitize_nul(filename or "attachment"))
    display_filename = Path(display_filename).name.strip()
    if display_filename in {"", ".", ".."}:
        return "attachment"
    return display_filename


def _coerce_deferred_payload_bytes(raw_content: Any) -> bytes:
    """Return the exact byte payload retained for deferred recognition."""
    if isinstance(raw_content, bytes):
        return raw_content
    if isinstance(raw_content, str):
        return raw_content.encode("utf-8", errors="surrogatepass")
    if raw_content is None:
        return b""
    return str(raw_content).encode("utf-8", errors="surrogatepass")


def _encode_deferred_payload(payload: bytes) -> str:
    """Base64-encode validated bytes retained for deferred recognition."""
    return base64.b64encode(payload).decode("ascii")


def decode_deferred_attachment_payload(
    content: str | None,
    expected_content_type: str = "application/pdf",
) -> bytes:
    """Decode the base64 payload retained on a pending attachment's content.

    Raises ``ValueError`` when the stored payload is not valid base64 or no
    longer matches the expected deferred parser family, so the recognition
    worker can record an error status instead of crashing.
    """
    parse_content_type = _normalize_content_type(expected_content_type)
    if parse_content_type not in _DEFERRED_DESCRIPTORS_BY_CONTENT_TYPE:
        raise ValueError(
            "Pending attachment content type is not a deferred parser type"
        )
    try:
        payload = base64.b64decode((content or "").encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("Pending attachment payload is not valid base64") from exc
    if len(payload) > MAX_ATTACHMENT_PARSE_SOURCE_BYTES:
        raise ValueError("Pending attachment payload exceeds the parse size limit")
    payload_error_code = _deferred_payload_error_code(parse_content_type, payload)
    if payload_error_code is not None:
        raise ValueError(_DEFERRED_PAYLOAD_ERROR_MESSAGES[payload_error_code])
    return payload


def _deferred_payload_error_code(
    parse_content_type: str,
    payload: bytes,
) -> str | None:
    """Return an error code when deferred parser bytes fail a cheap signature."""
    if parse_content_type == "application/pdf" and not payload.startswith(b"%PDF-"):
        return "invalid_pdf_payload"
    if parse_content_type in _HWPX_CONTENT_TYPES and not _is_hwpx_payload(payload):
        return "invalid_hwpx_payload"
    if parse_content_type in _HWP_CONTENT_TYPES and not _is_hwp_payload(payload):
        return "invalid_hwp_payload"
    return None


def _bounded_zip_directory_metadata(payload: bytes) -> tuple[int, int] | None:
    """Return bounded ZIP directory counts without materializing member metadata."""
    search_start = max(
        0,
        len(payload) - (_ZIP_END_RECORD_SIZE + _ZIP_MAX_COMMENT_BYTES),
    )
    record_offset = payload.rfind(_ZIP_END_RECORD_SIGNATURE, search_start)
    if record_offset < 0 or record_offset + _ZIP_END_RECORD_SIZE > len(payload):
        return None

    (
        signature,
        disk_number,
        directory_disk_number,
        disk_entry_count,
        total_entry_count,
        directory_size,
        directory_offset,
        comment_size,
    ) = _ZIP_END_RECORD.unpack_from(payload, record_offset)
    if (
        signature != _ZIP_END_RECORD_SIGNATURE
        or disk_number != 0
        or directory_disk_number != 0
        or disk_entry_count != total_entry_count
        or not 0 < total_entry_count <= MAX_HWPX_ZIP_ENTRIES
        or directory_size > MAX_HWPX_CENTRAL_DIRECTORY_BYTES
        or record_offset + _ZIP_END_RECORD_SIZE + comment_size != len(payload)
        or directory_offset + directory_size > record_offset
    ):
        return None
    return total_entry_count, directory_size


def _is_hwpx_payload(payload: bytes) -> bool:
    """Return whether bytes look like a bounded HWPX/OWPML ZIP package.

    Recognition checks ZIP directory budgets and the exact HWPX ``mimetype``
    signature before inspecting only member names. It does not parse section XML,
    execute active content, extract files, or fetch external resources.
    """
    directory_metadata = _bounded_zip_directory_metadata(payload)
    if not payload.startswith(b"PK") or directory_metadata is None:
        return False
    expected_entry_count, _ = directory_metadata

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            aggregate_name_bytes = sum(
                len(entry.filename.encode("utf-8", errors="surrogatepass"))
                for entry in entries
            )
            if (
                len(entries) != expected_entry_count
                or aggregate_name_bytes > MAX_HWPX_ZIP_NAME_BYTES
            ):
                return False

            mimetype_entries = [
                entry for entry in entries if entry.filename == "mimetype"
            ]
            if len(mimetype_entries) != 1:
                return False
            mimetype_entry = mimetype_entries[0]
            if (
                mimetype_entry.flag_bits & 0x1
                or mimetype_entry.file_size > MAX_HWPX_MIMETYPE_BYTES
            ):
                return False
            mimetype = archive.read(mimetype_entry)
            names = {entry.filename for entry in entries}
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
    ):
        return False

    has_manifest = "Contents/content.hpf" in names or "META-INF/manifest.xml" in names
    has_section = any(
        name.startswith("Contents/section") and name.endswith(".xml")
        for name in names
    )
    return (
        mimetype == _HWPX_MIMETYPE
        and "version.xml" in names
        and (has_manifest or has_section)
    )


def _is_hwp_payload(payload: bytes) -> bool:
    """Require both the OLE container magic and HWP FileHeader identity."""
    if not payload.startswith(_HWP_OLE_MAGIC):
        return False
    return payload.find(_HWP_DOCUMENT_SIGNATURE, len(_HWP_OLE_MAGIC)) >= 0


def _coerce_text(raw_content: Any) -> str:
    """Coerce arbitrary attachment content to NUL-free text."""
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return _sanitize_nul(raw_content)
    if isinstance(raw_content, bytes):
        return _sanitize_nul(raw_content.decode("utf-8", errors="replace"))
    return _sanitize_nul(str(raw_content))


def _display_text(raw_content: str) -> str:
    """Strip markup and collapse whitespace for safe attachment display."""
    return " ".join(strip_html_markup(raw_content).split())


def _sanitize_nul(text: str) -> str:
    """Remove NUL characters that database text fields cannot retain."""
    return text.replace("\x00", "")
