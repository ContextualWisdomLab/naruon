"""Admit and classify local email inline images without remote fetch or models.

This module is the #1350 Slice 3 admission contract. It resolves ``cid:``
references against the same message's ``multipart/related`` parts, classifies
admitted images into a closed set, and returns hash plus part-index
provenance. It does not call OCR, a VLM, NewsDOM, or any LLM, does not
mutate provider mail, and does not fetch ``http`` or ``https`` image URLs.
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser

DOCUMENT_IMAGE_CLASSIFICATION = "document_image"
TRACKING_PIXEL_CLASSIFICATION = "tracking_pixel"
UNSUPPORTED_MEDIA_CLASSIFICATION = "unsupported_media"

KNOWN_EVIDENCE_BOUNDARY = "known"
UNKNOWN_EVIDENCE_BOUNDARY = "unknown"

UNRESOLVED_CID_ERROR_CODE = "unresolved_cid_reference"
REMOTE_FETCH_POLICY = "disabled"

TRACKING_PIXEL_MAX_EDGE = 1
TINY_TRACKER_GIF_MAX_BYTES = 48

SUPPORTED_IMAGE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)
IMAGE_TYPE_ALIASES = {"image/jpg": "image/jpeg"}
TRACKER_CONTENT_TYPES = frozenset({"image/gif"})
TRACKER_HOST_SUFFIXES = (
    "list-manage.com",
    "doubleclick.net",
    "google-analytics.com",
    "googletagmanager.com",
    "adsrvr.org",
)
TRACKER_PATH_MARKERS = (
    "/track/open",
    "/pixel.gif",
    "/open.gif",
    "/open.php",
)

_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
_IMG_SRC_RE = re.compile(
    r"""<img\b[^>]*\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class InlineImageAdmission:
    """Provenance and closed-set classification for one local MIME image part."""

    source_part_index: int
    content_id: str | None
    content_sha256: str
    media_classification: str
    evidence_boundary: str
    error_code: str | None
    declared_content_type: str
    content_location: str | None
    pixel_width: int | None
    pixel_height: int | None


@dataclass(frozen=True)
class CidReferenceAdmission:
    """Outcome of one ``cid:`` HTML reference against related MIME parts."""

    raw_reference: str
    content_id: str | None
    source_part_index: int | None
    content_sha256: str | None
    media_classification: str | None
    error_code: str | None
    evidence_boundary: str | None


@dataclass(frozen=True)
class EmailMediaAdmissionResult:
    """Admission outcomes for one raw RFC 5322 message."""

    inline_images: tuple[InlineImageAdmission, ...]
    cid_references: tuple[CidReferenceAdmission, ...]
    remote_fetch_policy: str = REMOTE_FETCH_POLICY


@dataclass(frozen=True)
class _RelatedImagePart:
    """Internal related-scope image part used only during CID matching."""

    related_scope: str | None
    content_id: str | None
    admission: InlineImageAdmission


def admit_email_inline_media(raw_message: bytes) -> EmailMediaAdmissionResult:
    """Admit local inline images and resolve same-message ``cid:`` references.

    Remote ``http(s)`` image references are ignored for admission and are never
    downloaded. Unresolved ``cid:`` references fail closed with
    ``unresolved_cid_reference`` and are not treated as document evidence.

    Args:
        raw_message: Complete RFC 5322 message bytes, including MIME headers.

    Returns:
        Classified local image parts plus every HTML ``cid:`` outcome.

    Raises:
        TypeError: If ``raw_message`` is not ``bytes``.
    """
    if not isinstance(raw_message, bytes):
        raise TypeError("raw_message must be bytes")

    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    images: list[_RelatedImagePart] = []
    html_parts: list[tuple[str | None, str]] = []
    part_index_holder = [0]
    _collect_message_parts(
        message,
        path="0",
        related_scope=None,
        part_index_holder=part_index_holder,
        images=images,
        html_parts=html_parts,
    )

    cid_references: list[CidReferenceAdmission] = []
    for related_scope, html_source in html_parts:
        for raw_reference in _html_image_references(html_source):
            if _is_remote_reference(raw_reference):
                continue
            if not raw_reference.casefold().startswith("cid:"):
                continue
            cid_references.append(
                _resolve_cid_reference(
                    raw_reference=raw_reference,
                    related_scope=related_scope,
                    images=images,
                )
            )

    return EmailMediaAdmissionResult(
        inline_images=tuple(item.admission for item in images),
        cid_references=tuple(cid_references),
    )


def _collect_message_parts(
    part: Message,
    *,
    path: str,
    related_scope: str | None,
    part_index_holder: list[int],
    images: list[_RelatedImagePart],
    html_parts: list[tuple[str | None, str]],
) -> None:
    """Walk one MIME subtree and collect HTML plus local image parts."""
    current_scope = (
        path if part.get_content_type() == "multipart/related" else related_scope
    )
    children = _message_children(part)
    if children:
        for child_index, child in enumerate(children):
            _collect_message_parts(
                child,
                path=f"{path}.{child_index}",
                related_scope=current_scope,
                part_index_holder=part_index_holder,
                images=images,
                html_parts=html_parts,
            )
        return

    source_part_index = part_index_holder[0]
    part_index_holder[0] += 1
    declared_content_type = _normalize_content_type(part.get_content_type())
    if declared_content_type == "text/html":
        html_parts.append((current_scope, _decode_text_part(part)))
        return
    if part.get_content_maintype().casefold() != "image":
        return

    raw_payload = part.get_payload(decode=True)
    payload_bytes = raw_payload if isinstance(raw_payload, bytes) else b""
    images.append(
        _build_related_image_part(
            source_part_index=source_part_index,
            related_scope=current_scope,
            content_id=_normalize_content_id(part.get("Content-ID")),
            content_location=_header_text(part.get("Content-Location")),
            declared_content_type=declared_content_type,
            payload_bytes=payload_bytes,
        )
    )


def _build_related_image_part(
    *,
    source_part_index: int,
    related_scope: str | None,
    content_id: str | None,
    content_location: str | None,
    declared_content_type: str,
    payload_bytes: bytes,
) -> _RelatedImagePart:
    """Classify one decoded image part and retain its related-scope identity."""
    classification, evidence_boundary, pixel_width, pixel_height = _classify_image(
        declared_content_type=declared_content_type,
        payload_bytes=payload_bytes,
        content_location=content_location,
    )
    admission = InlineImageAdmission(
        source_part_index=source_part_index,
        content_id=content_id,
        content_sha256=hashlib.sha256(payload_bytes).hexdigest(),
        media_classification=classification,
        evidence_boundary=evidence_boundary,
        error_code=None,
        declared_content_type=declared_content_type,
        content_location=content_location,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
    )
    return _RelatedImagePart(
        related_scope=related_scope,
        content_id=content_id,
        admission=admission,
    )


def _classify_image(
    *,
    declared_content_type: str,
    payload_bytes: bytes,
    content_location: str | None,
) -> tuple[str, str, int | None, int | None]:
    """Return classification, evidence boundary, and header-derived dimensions."""
    inferred_content_type = _infer_image_content_type(payload_bytes)
    if (
        declared_content_type not in SUPPORTED_IMAGE_TYPES
        or inferred_content_type is None
        or inferred_content_type != declared_content_type
    ):
        return (
            UNSUPPORTED_MEDIA_CLASSIFICATION,
            KNOWN_EVIDENCE_BOUNDARY,
            None,
            None,
        )

    dimensions = _pixel_dimensions_from_header(declared_content_type, payload_bytes)
    pixel_width, pixel_height = dimensions if dimensions is not None else (None, None)
    if _is_tracking_pixel(
        pixel_width=pixel_width,
        pixel_height=pixel_height,
        declared_content_type=declared_content_type,
        content_location=content_location,
        payload_bytes=payload_bytes,
    ):
        return (
            TRACKING_PIXEL_CLASSIFICATION,
            KNOWN_EVIDENCE_BOUNDARY,
            pixel_width,
            pixel_height,
        )
    if pixel_width is None or pixel_height is None:
        return (
            DOCUMENT_IMAGE_CLASSIFICATION,
            UNKNOWN_EVIDENCE_BOUNDARY,
            pixel_width,
            pixel_height,
        )
    return (
        DOCUMENT_IMAGE_CLASSIFICATION,
        KNOWN_EVIDENCE_BOUNDARY,
        pixel_width,
        pixel_height,
    )


def _is_tracking_pixel(
    *,
    pixel_width: int | None,
    pixel_height: int | None,
    declared_content_type: str,
    content_location: str | None,
    payload_bytes: bytes,
) -> bool:
    """Decide tracking-pixel admission from local evidence only.

    Evidence is header-derived pixel size, an already-present Content-Location
    tracker pattern, or a typical tracker content-type with a tiny GIF payload.
    Remote pixels are never downloaded.
    """
    if (
        pixel_width is not None
        and pixel_height is not None
        and pixel_width <= TRACKING_PIXEL_MAX_EDGE
        and pixel_height <= TRACKING_PIXEL_MAX_EDGE
    ):
        return True
    if _content_location_matches_tracker(content_location):
        return True
    return (
        declared_content_type in TRACKER_CONTENT_TYPES
        and (pixel_width is None or pixel_height is None)
        and 0 < len(payload_bytes) <= TINY_TRACKER_GIF_MAX_BYTES
    )


def _content_location_matches_tracker(content_location: str | None) -> bool:
    """Match known tracker hosts or paths on an already-present header value."""
    if content_location is None:
        return False
    try:
        parsed_url = urllib.parse.urlsplit(content_location)
    except ValueError:
        return False
    host_name = (parsed_url.hostname or "").casefold()
    path_value = (parsed_url.path or "").casefold()
    if any(
        host_name == suffix or host_name.endswith(f".{suffix}")
        for suffix in TRACKER_HOST_SUFFIXES
    ):
        return True
    return any(marker in path_value for marker in TRACKER_PATH_MARKERS)


def _resolve_cid_reference(
    *,
    raw_reference: str,
    related_scope: str | None,
    images: list[_RelatedImagePart],
) -> CidReferenceAdmission:
    """Bind one ``cid:`` URL to a unique related-scope Content-ID, or fail closed."""
    content_id = _normalize_cid_url(raw_reference)
    if content_id is None or related_scope is None:
        return _unresolved_cid_reference(raw_reference, content_id)

    candidates = [
        image
        for image in images
        if image.related_scope == related_scope and image.content_id == content_id
    ]
    if len(candidates) != 1:
        return _unresolved_cid_reference(raw_reference, content_id)

    admission = candidates[0].admission
    return CidReferenceAdmission(
        raw_reference=raw_reference,
        content_id=content_id,
        source_part_index=admission.source_part_index,
        content_sha256=admission.content_sha256,
        media_classification=admission.media_classification,
        error_code=None,
        evidence_boundary=admission.evidence_boundary,
    )


def _unresolved_cid_reference(
    raw_reference: str, content_id: str | None
) -> CidReferenceAdmission:
    """Return the stable fail-closed outcome for a CID that cannot be bound."""
    return CidReferenceAdmission(
        raw_reference=raw_reference,
        content_id=content_id,
        source_part_index=None,
        content_sha256=None,
        media_classification=None,
        error_code=UNRESOLVED_CID_ERROR_CODE,
        evidence_boundary=KNOWN_EVIDENCE_BOUNDARY,
    )


def _html_image_references(html_source: str) -> list[str]:
    """Extract raw ``img`` ``src`` values without fetching or rewriting them."""
    references: list[str] = []
    for match in _IMG_SRC_RE.finditer(html_source):
        raw_value = next(
            group for group in match.groups() if group is not None
        )
        references.append(raw_value.strip())
    return references


def _message_children(part: Message) -> list[Message]:
    """Return multipart children, ignoring non-message payload entries."""
    payload = part.get_payload()
    if not part.is_multipart() or not isinstance(payload, list):
        return []
    return [child for child in payload if isinstance(child, Message)]


def _decode_text_part(part: Message) -> str:
    """Decode a text MIME part, replacing undecodable bytes."""
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")
    content = part.get_payload()
    return content if isinstance(content, str) else ""


def _normalize_cid_url(reference: str) -> str | None:
    """Convert a ``cid:`` URL into a Content-ID token per RFC 2392."""
    if not reference.casefold().startswith("cid:"):
        return None
    encoded_value = reference[4:]
    try:
        decoded_value = urllib.parse.unquote(encoded_value, errors="strict")
    except UnicodeDecodeError:
        return None
    if (
        not decoded_value
        or _CONTROL_CHARACTER_RE.search(decoded_value)
        or any(character.isspace() for character in decoded_value)
    ):
        return None
    return decoded_value


def _normalize_content_id(value: object) -> str | None:
    """Normalize a Content-ID header by stripping angle brackets."""
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1]
    if (
        not normalized
        or _CONTROL_CHARACTER_RE.search(normalized)
        or any(character.isspace() for character in normalized)
    ):
        return None
    return normalized


def _normalize_content_type(value: str) -> str:
    """Return a lowercase media type without parameters."""
    normalized = (value or "").split(";", 1)[0].strip().casefold()
    return IMAGE_TYPE_ALIASES.get(normalized, normalized)


def _header_text(value: object) -> str | None:
    """Return a stripped header string, or ``None`` when absent or blank."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _infer_image_content_type(payload: bytes) -> str | None:
    """Infer a supported image type from a deterministic file signature."""
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return None


def _pixel_dimensions_from_header(
    content_type: str, payload: bytes
) -> tuple[int, int] | None:
    """Read PNG IHDR or GIF logical-screen size without decoding pixels.

    This helper exists only for the Slice 3 tracking-pixel heuristic. It does
    not implement or replace the #1376 ``EmailMediaArtifact`` pixel-dimension
    contract, which is not present on protected ``develop``.
    """
    if (
        content_type == "image/png"
        and len(payload) >= 24
        and payload.startswith(b"\x89PNG\r\n\x1a\n")
    ):
        return (
            int.from_bytes(payload[16:20], "big"),
            int.from_bytes(payload[20:24], "big"),
        )
    if (
        content_type == "image/gif"
        and len(payload) >= 10
        and payload.startswith((b"GIF87a", b"GIF89a"))
    ):
        return (
            int.from_bytes(payload[6:8], "little"),
            int.from_bytes(payload[8:10], "little"),
        )
    return None


def _is_remote_reference(reference: str) -> bool:
    """Return True for ``http`` or ``https`` URLs that must not be fetched."""
    try:
        scheme = urllib.parse.urlsplit(reference).scheme.casefold()
    except ValueError:
        return False
    return scheme in {"http", "https"}
