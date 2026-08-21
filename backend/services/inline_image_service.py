"""Extract safe, source-linked evidence for base64 images embedded in HTML."""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import unquote_to_bytes

from .attachment_parser import (
    SUPPORTED_IMAGE_CONTENT_TYPES,
    ImageMetadata,
    inspect_image_metadata,
)

MAX_INLINE_IMAGE_BYTES = 64 * 1024 * 1024
MAX_INLINE_IMAGE_COUNT = 1_000
MAX_INLINE_IMAGE_ENCODED_CHARS = ((MAX_INLINE_IMAGE_BYTES + 2) // 3) * 4 + 4
MAX_INLINE_IMAGE_MEDIA_TYPE_CHARS = 120
_VOID_HTML_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
_INLINE_IMAGE_SRC_RE = re.compile(
    r"(?P<prefix>\bsrc\s*=\s*)(?P<quote>['\"])(?P<uri>data:image/[^'\"\s>]*)(?P=quote)",
    re.IGNORECASE,
)
_INLINE_IMAGE_UNQUOTED_SRC_RE = re.compile(
    r"(?P<prefix>\bsrc\s*=\s*)(?P<uri>data:image/[^\s>]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class InlineImageSource:
    """Represent one inline image without storing its source bytes."""

    source_locator_type: str
    source_locator_value: str
    source_ordinal: int
    media_type: str
    byte_count: int | None
    content_digest: str | None
    detected_format: str | None
    pixel_width: int | None
    pixel_height: int | None
    is_animated: bool | None
    parse_status: str
    parse_error_code: str | None

    @property
    def searchable_text(self) -> str:
        """Return bounded metadata suitable for the existing text index."""
        fields = [
            "Inline image evidence",
            f"media_type={self.media_type}",
            f"source_locator={self.source_locator_value}",
            f"status={self.parse_status}",
        ]
        if self.byte_count is not None:
            fields.append(f"bytes={self.byte_count}")
        if self.content_digest is not None:
            fields.append(f"digest={self.content_digest}")
        if self.detected_format is not None:
            fields.append(f"format={self.detected_format}")
        if self.pixel_width is not None and self.pixel_height is not None:
            fields.append(f"width={self.pixel_width}px")
            fields.append(f"height={self.pixel_height}px")
        if self.is_animated is not None:
            fields.append(f"animated={'yes' if self.is_animated else 'no'}")
        if self.parse_error_code is not None:
            fields.append(f"error={self.parse_error_code}")
        return "; ".join(fields)

    def as_payload(self) -> dict[str, object]:
        """Return the persistence-neutral representation used by email import."""
        return {
            "source_locator_type": self.source_locator_type,
            "source_locator_value": self.source_locator_value,
            "source_ordinal": self.source_ordinal,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "content_digest": self.content_digest,
            "detected_format": self.detected_format,
            "pixel_width": self.pixel_width,
            "pixel_height": self.pixel_height,
            "is_animated": self.is_animated,
            "parse_status": self.parse_status,
            "parse_error_code": self.parse_error_code,
            "searchable_text": self.searchable_text,
        }


class _InlineImageParser(HTMLParser):
    """Track enough HTML structure to produce stable DOM-path locators."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._path_stack: list[tuple[str, int]] = []
        self._child_counts: list[dict[str, int]] = [{}]
        self._source_ordinal = 0
        self.sources: list[InlineImageSource] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_start(tag, attrs, self_closing=tag.lower() in _VOID_HTML_TAGS)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._handle_start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        matching_index = next(
            (
                index
                for index in range(len(self._path_stack) - 1, -1, -1)
                if self._path_stack[index][0] == normalized_tag
            ),
            None,
        )
        if matching_index is None:
            return
        del self._path_stack[matching_index:]
        del self._child_counts[matching_index + 1 :]

    def _handle_start(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        *,
        self_closing: bool,
    ) -> None:
        normalized_tag = tag.lower()
        parent_counts = self._child_counts[-1]
        child_index = parent_counts.get(normalized_tag, 0) + 1
        parent_counts[normalized_tag] = child_index
        self._path_stack.append((normalized_tag, child_index))
        path = "/" + "/".join(
            f"{current_tag}[{current_index}]"
            for current_tag, current_index in self._path_stack
        )
        if normalized_tag == "img" and len(self.sources) < MAX_INLINE_IMAGE_COUNT:
            attributes = {
                name.lower(): value or "" for name, value in attrs if name
            }
            source_value = attributes.get("src", "")
            if source_value.lower().startswith("data:"):
                self._source_ordinal += 1
                self.sources.append(
                    _parse_data_image_uri(
                        source_value,
                        source_locator_value=path,
                        source_ordinal=self._source_ordinal,
                    )
                )
        if self_closing:
            self._path_stack.pop()
        else:
            self._child_counts.append({})


def extract_inline_image_sources(html: str | None) -> tuple[InlineImageSource, ...]:
    """Extract bounded base64 ``img`` data URLs from one HTML body."""
    if not html:
        return ()
    parser = _InlineImageParser()
    parser.feed(html)
    parser.close()
    return tuple(parser.sources)


def redact_inline_image_payloads(html: str | None) -> str:
    """Remove base64 bytes before an HTML body reaches an embedding provider."""
    if not html:
        return ""

    def quoted_replacement(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        quote = match.group("quote")
        return f"{prefix}{quote}inline-image://bytes-omitted{quote}"

    def unquoted_replacement(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}inline-image://bytes-omitted"

    redacted = _INLINE_IMAGE_SRC_RE.sub(quoted_replacement, html)
    return _INLINE_IMAGE_UNQUOTED_SRC_RE.sub(unquoted_replacement, redacted)


def _parse_data_image_uri(
    value: str,
    *,
    source_locator_value: str,
    source_ordinal: int,
) -> InlineImageSource:
    """Decode one data URL strictly enough to avoid implicit byte retention."""
    prefix, separator, encoded_payload = value[5:].partition(",")
    media_tokens = [token.strip().lower() for token in prefix.split(";")]
    raw_media_type = media_tokens[0] or "application/octet-stream"
    media_type = (
        raw_media_type
        if len(raw_media_type) <= MAX_INLINE_IMAGE_MEDIA_TYPE_CHARS
        else "application/octet-stream"
    )
    base_fields = {
        "source_locator_type": "html_dom_path",
        "source_locator_value": source_locator_value,
        "source_ordinal": source_ordinal,
        "media_type": media_type,
        "byte_count": None,
        "content_digest": None,
        "detected_format": None,
        "pixel_width": None,
        "pixel_height": None,
        "is_animated": None,
    }
    if not separator:
        return InlineImageSource(
            **base_fields,
            parse_status="inline_image_parse_failed",
            parse_error_code="malformed_data_uri",
        )
    if media_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
        return InlineImageSource(
            **base_fields,
            parse_status="inline_image_not_supported",
            parse_error_code="unsupported_image_media_type",
        )
    if "base64" not in media_tokens[1:]:
        return InlineImageSource(
            **base_fields,
            parse_status="inline_image_not_supported",
            parse_error_code="unsupported_image_encoding",
        )
    if len(encoded_payload) > MAX_INLINE_IMAGE_ENCODED_CHARS:
        return InlineImageSource(
            **base_fields,
            parse_status="inline_image_size_limit_exceeded",
            parse_error_code="inline_image_size_limit_exceeded",
        )
    try:
        decoded_payload = unquote_to_bytes(encoded_payload)
        payload = base64.b64decode(decoded_payload, validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return InlineImageSource(
            **base_fields,
            parse_status="inline_image_parse_failed",
            parse_error_code="invalid_base64_payload",
        )
    if len(payload) > MAX_INLINE_IMAGE_BYTES:
        return InlineImageSource(
            **base_fields,
            parse_status="inline_image_size_limit_exceeded",
            parse_error_code="inline_image_size_limit_exceeded",
        )
    metadata = inspect_image_metadata(payload)
    digest = hashlib.sha256(payload).hexdigest()
    if metadata is None:
        return InlineImageSource(
            **{
                **base_fields,
                "byte_count": len(payload),
                "content_digest": digest,
                "parse_status": "inline_image_parse_failed",
                "parse_error_code": "invalid_image_payload",
            }
        )
    return _metadata_source(
        base_fields=base_fields,
        payload=payload,
        digest=digest,
        metadata=metadata,
    )


def _metadata_source(
    *,
    base_fields: dict[str, object],
    payload: bytes,
    digest: str,
    metadata: ImageMetadata,
) -> InlineImageSource:
    """Build a successful source record from bounded header facts."""
    return InlineImageSource(
        **{
            **base_fields,
            "byte_count": len(payload),
            "content_digest": digest,
            "detected_format": metadata.format_name,
            "pixel_width": metadata.width,
            "pixel_height": metadata.height,
            "is_animated": metadata.animated,
        },
        parse_status="metadata_ready",
        parse_error_code=None,
    )
