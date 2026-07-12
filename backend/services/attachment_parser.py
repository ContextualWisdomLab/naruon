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
MAX_ATTACHMENT_PARSE_SOURCE_CHARS = 1_000_000


@dataclass(frozen=True)
class AttachmentParserDescriptor:
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
    filename: str
    content: str
    content_type: str
    parse_content: str
    parse_content_type: str
    parser_key: str
    parse_status: str
    parse_error_code: str | None


def get_attachment_parser_manifest() -> list[AttachmentParserDescriptor]:
    return list(_PARSER_MANIFEST)


def parse_email_attachment(
    *,
    filename: str | None,
    content_type: str | None,
    raw_content: Any,
) -> AttachmentParseResult:
    safe_filename = _safe_filename(filename)
    normalized_content_type = _normalize_content_type(content_type)
    parse_content_type = _parse_content_type_for(
        safe_filename,
        normalized_content_type,
    )

    deferred_descriptor = _DEFERRED_DESCRIPTORS_BY_CONTENT_TYPE.get(parse_content_type)
    if deferred_descriptor is not None:
        # Heavy recognition (OCR/MinerU via the NewsDOM sidecar) must not run
        # inline during import — mark the attachment pending and let the worker
        # populate parse_content + the content graph.
        return AttachmentParseResult(
            filename=safe_filename,
            content="",
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
    normalized = (content_type or "application/octet-stream").split(";", 1)[0]
    normalized = normalized.strip().lower()
    return normalized or "application/octet-stream"


def _parse_content_type_for(filename: str, content_type: str) -> str:
    if content_type not in _GENERIC_CONTENT_TYPES:
        return content_type
    extension = Path(filename).suffix.lower()
    return _EXTENSION_CONTENT_TYPES.get(extension, content_type)


def _parser_key_for(parse_content_type: str, parse_status: str) -> str:
    if parse_status == "unsupported_content_type":
        return "unsupported_binary"
    for descriptor in _PARSER_MANIFEST:
        if parse_content_type in descriptor.content_types:
            return descriptor.parser_key
    return "unsupported_binary"


def _safe_filename(filename: str | None) -> str:
    display_filename = strip_html_markup(_sanitize_nul(filename or "attachment"))
    display_filename = Path(display_filename).name.strip()
    if display_filename in {"", ".", ".."}:
        return "attachment"
    return display_filename


def _coerce_text(raw_content: Any) -> str:
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return _sanitize_nul(raw_content)
    if isinstance(raw_content, bytes):
        return _sanitize_nul(raw_content.decode("utf-8", errors="replace"))
    return _sanitize_nul(str(raw_content))


def _display_text(raw_content: str) -> str:
    return " ".join(strip_html_markup(raw_content).split())


def _sanitize_nul(text: str) -> str:
    return text.replace("\x00", "")
