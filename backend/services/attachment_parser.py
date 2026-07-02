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
_SUPPORTED_CONTENT_TYPES = {
    "text/plain",
    "text/html",
    "text/markdown",
    "text/x-markdown",
    "application/markdown",
}
_EXTENSION_CONTENT_TYPES = {
    ".txt": "text/plain",
    ".text": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


@dataclass(frozen=True)
class AttachmentParseResult:
    filename: str
    content: str
    content_type: str
    parse_content: str
    parse_content_type: str
    parse_status: str
    parse_error_code: str | None


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

    if parse_content_type not in _SUPPORTED_CONTENT_TYPES:
        return AttachmentParseResult(
            filename=safe_filename,
            content="",
            content_type=normalized_content_type,
            parse_content="",
            parse_content_type=normalized_content_type,
            parse_status="unsupported_content_type",
            parse_error_code="unsupported_content_type",
        )

    parse_content = _coerce_text(raw_content).strip()
    return AttachmentParseResult(
        filename=safe_filename,
        content=_display_text(parse_content),
        content_type=normalized_content_type,
        parse_content=parse_content,
        parse_content_type=parse_content_type,
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
