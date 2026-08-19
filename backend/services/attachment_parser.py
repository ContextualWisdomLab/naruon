"""Classify email attachments and retain safe deferred parser inputs."""

import base64
import binascii
from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Any

from .text_safety import strip_html_markup

_GENERIC_CONTENT_TYPES = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
    "application/x-binary",
}
MAX_ATTACHMENT_PARSE_SOURCE_CHARS = 1_000_000
MAX_ATTACHMENT_PARSE_SOURCE_BYTES = 20 * 1024 * 1024


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
        parser_key="image_metadata",
        display_name="Image metadata attachments",
        content_types=("image/png", "image/jpeg", "image/gif", "image/bmp"),
        extensions=(".png", ".jpg", ".jpeg", ".gif", ".bmp"),
        parse_status="parsed",
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
# calls the NewsDOM sidecar to fill in parse_content + the content graph.
_DEFERRED_PARSE_STATUSES = frozenset({"pdf_dom_recognition_pending"})
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
        # Heavy recognition (OCR/MinerU via the NewsDOM sidecar) must not run
        # inline during import. Retain the raw bytes as a base64 payload in
        # ``content`` (mirroring the document-upload path's document_content) so
        # the worker can decode and recognize them later; mark the attachment
        # pending. The pending status gates display, and the worker overwrites
        # ``content`` with the recognized text on success. Without this the
        # source bytes were discarded and recognition was impossible.
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
        if parse_content_type == "application/pdf" and not deferred_payload.startswith(
            b"%PDF-"
        ):
            return AttachmentParseResult(
                filename=safe_filename,
                content="",
                content_type=normalized_content_type,
                parse_content="",
                parse_content_type=parse_content_type,
                parser_key=deferred_descriptor.parser_key,
                parse_status="invalid_pdf_payload",
                parse_error_code="invalid_pdf_payload",
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

    if parse_content_type in _IMAGE_CONTENT_TYPES:
        image_payload = _coerce_deferred_payload_bytes(raw_content)
        if len(image_payload) > MAX_ATTACHMENT_PARSE_SOURCE_BYTES:
            return AttachmentParseResult(
                filename=safe_filename,
                content="",
                content_type=normalized_content_type,
                parse_content="",
                parse_content_type=parse_content_type,
                parser_key="image_metadata",
                parse_status="parse_size_limit_exceeded",
                parse_error_code="parse_size_limit_exceeded",
            )

        metadata = _parse_image_metadata(image_payload)
        if metadata is None:
            return AttachmentParseResult(
                filename=safe_filename,
                content="",
                content_type=normalized_content_type,
                parse_content="",
                parse_content_type=parse_content_type,
                parser_key="image_metadata",
                parse_status="image_metadata_parse_failed",
                parse_error_code="image_metadata_parse_failed",
            )
        return AttachmentParseResult(
            filename=safe_filename,
            content=metadata,
            content_type=normalized_content_type,
            parse_content=metadata,
            parse_content_type="text/plain",
            parser_key="image_metadata",
            parse_status="parsed",
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


def decode_deferred_attachment_payload(content: str | None) -> bytes:
    """Decode the base64 payload retained on a pending attachment's content.

    Raises ``ValueError`` when the stored payload is not valid base64, so the
    recognition worker can record an error status instead of crashing.
    """
    try:
        payload = base64.b64decode((content or "").encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("Pending attachment payload is not valid base64") from exc
    if len(payload) > MAX_ATTACHMENT_PARSE_SOURCE_BYTES:
        raise ValueError("Pending attachment PDF exceeds the parse size limit")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("Pending attachment payload is not a PDF")
    return payload


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


_IMAGE_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/bmp"})
_JPEG_SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)


def _parse_image_metadata(payload: bytes) -> str | None:
    """Read bounded image headers into searchable text without decoding pixels."""
    if payload.startswith(b"\x89PNG"):
        dimensions = _png_dimensions(payload)
        format_name = "png"
        animated = b"acTL" in payload[:MAX_ATTACHMENT_PARSE_SOURCE_BYTES]
    elif payload.startswith(b"\xff\xd8"):
        dimensions = _jpeg_dimensions(payload)
        format_name = "jpeg"
        animated = False
    elif payload[:6] in {b"GIF87a", b"GIF89a"}:
        dimensions = _gif_dimensions(payload)
        format_name = "gif"
        animated = b"NETSCAPE2.0" in payload[:MAX_ATTACHMENT_PARSE_SOURCE_BYTES]
    elif payload.startswith(b"BM"):
        dimensions = _bmp_dimensions(payload)
        format_name = "bmp"
        animated = False
    else:
        return None

    if dimensions is None:
        return None
    width, height = dimensions
    return (
        "Image metadata: "
        f"format={format_name}; width={width}px; height={height}px; "
        f"animated={'yes' if animated else 'no'}"
    )


def _png_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if payload[12:16] != b"IHDR" or int.from_bytes(payload[8:12], "big") < 13:
        return None
    width, height = struct.unpack(">II", payload[16:24])
    return (width, height) if width and height else None


def _jpeg_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 4 or payload[:2] != b"\xff\xd8":
        return None
    position = 2
    while position + 1 < len(payload):
        if payload[position] != 0xFF:
            return None
        while position < len(payload) and payload[position] == 0xFF:
            position += 1
        if position >= len(payload):
            return None
        marker = payload[position]
        position += 1
        if marker == 0x00:
            continue
        if marker == 0xDA:
            return None
        if marker == 0x01 or 0xD0 <= marker <= 0xD9:
            continue
        if position + 2 > len(payload):
            return None
        segment_length = int.from_bytes(payload[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(payload):
            return None
        if marker in _JPEG_SOF_MARKERS and segment_length >= 7:
            height = int.from_bytes(payload[position + 3 : position + 5], "big")
            width = int.from_bytes(payload[position + 5 : position + 7], "big")
            return (width, height) if width and height else None
        position += segment_length
    return None


def _gif_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 10 or payload[:6] not in {b"GIF87a", b"GIF89a"}:
        return None
    width, height = struct.unpack("<HH", payload[6:10])
    return (width, height) if width and height else None


def _bmp_dimensions(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 26 or payload[:2] != b"BM":
        return None
    dib_size = int.from_bytes(payload[14:18], "little")
    if dib_size == 12:
        width, height = struct.unpack("<HH", payload[18:22])
    elif dib_size >= 40:
        width = abs(struct.unpack("<i", payload[18:22])[0])
        height = abs(struct.unpack("<i", payload[22:26])[0])
    else:
        return None
    return (width, height) if width and height else None


def _sanitize_nul(text: str) -> str:
    """Remove NUL characters that database text fields cannot retain."""
    return text.replace("\x00", "")
