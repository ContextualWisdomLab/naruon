"""Resolve local email image evidence without fetching remote resources.

The resolver is intentionally deterministic. It parses raw MIME, binds ``cid:``
references to body parts inside the nearest ``multipart/related`` scope, decodes
bounded base64 ``data:`` images, and records remote image references without
performing network I/O. Semantic image classification is deliberately left to a
later evidence-bound vision stage.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import re
import urllib.parse
from dataclasses import dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser
from html.parser import HTMLParser

MAX_EMAIL_MEDIA_MESSAGE_BYTES = 25 * 1024 * 1024
MAX_EMAIL_MEDIA_IMAGE_BYTES = 10 * 1024 * 1024
MAX_EMAIL_MEDIA_HTML_CHARS = 2_000_000
MAX_EMAIL_MEDIA_REFERENCES = 500
MAX_EMAIL_MEDIA_ARTIFACTS = 100
MAX_EMAIL_MEDIA_OCCURRENCES = 1_000

_SUPPORTED_IMAGE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)
_IMAGE_TYPE_ALIASES = {"image/jpg": "image/jpeg"}
_SRC_ATTRIBUTE_RE = re.compile(
    r"(?is)\bsrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+))"
)
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class EmailMediaArtifact:
    """Represent one content-addressed image artifact and its safety state."""

    artifact_id: str
    content_sha256: str
    content_type: str
    byte_length: int
    payload_bytes: bytes
    llm_safe: bool
    visual_classification: str
    reason_code: str


@dataclass(frozen=True)
class EmailMediaOccurrence:
    """Record where a media payload or HTML image reference appeared."""

    occurrence_kind: str
    source_path: str
    source_start: int | None
    source_end: int | None
    raw_reference: str | None
    normalized_reference: str | None
    content_id: str | None
    artifact_id: str | None
    resolution_status: str
    reason_code: str


@dataclass(frozen=True)
class EmailMediaResolution:
    """Return deduplicated artifacts plus complete local/remote provenance."""

    artifacts: tuple[EmailMediaArtifact, ...]
    occurrences: tuple[EmailMediaOccurrence, ...]
    remote_fetch_policy: str = "disabled"


@dataclass(frozen=True)
class _MimeImagePart:
    path: str
    related_scope: str | None
    content_id: str | None
    artifact_id: str
    llm_safe: bool


class _ImageSourceParser(HTMLParser):
    """Extract IMG source values while retaining exact character offsets."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self._line_offsets = _line_offsets(source)
        self.references: list[tuple[str, int, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() != "img":
            return
        raw_tag = self.get_starttag_text() or ""
        match = _SRC_ATTRIBUTE_RE.search(raw_tag)
        if match is None:
            return
        value_group = next(
            index for index in (1, 2, 3) if match.group(index) is not None
        )
        raw_value = match.group(value_group)
        line_number, column_number = self.getpos()
        tag_start = self._line_offsets[line_number - 1] + column_number
        value_start = tag_start + match.start(value_group)
        self.references.append((raw_value, value_start, value_start + len(raw_value)))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)


def resolve_email_media(raw_message: bytes) -> EmailMediaResolution:
    """Resolve bounded local image evidence from one raw RFC 5322 message.

    Remote HTTP(S) references are recorded as ``remote_blocked`` and are never
    dereferenced. Unsupported or content-type-mismatched image payloads remain
    visible as non-LLM-safe artifacts so downstream callers cannot mistake an
    omission for a successful normalization.

    Raises:
        TypeError: If ``raw_message`` is not bytes.
        ValueError: If the raw message exceeds a deterministic resource bound or
            contains too many media artifacts, references, or occurrences.
    """
    if not isinstance(raw_message, bytes):
        raise TypeError("raw_message must be bytes")
    if len(raw_message) > MAX_EMAIL_MEDIA_MESSAGE_BYTES:
        raise ValueError("email_media_message_size_limit_exceeded")

    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    artifacts: dict[str, EmailMediaArtifact] = {}
    occurrences: list[EmailMediaOccurrence] = []
    mime_images: list[_MimeImagePart] = []
    html_parts: list[tuple[str, str | None, str]] = []

    _collect_message_parts(
        message,
        path="0",
        related_scope=None,
        artifacts=artifacts,
        occurrences=occurrences,
        mime_images=mime_images,
        html_parts=html_parts,
    )

    reference_count = 0
    for html_path, related_scope, html_source in html_parts:
        reference_count += _resolve_html_references(
            html_path=html_path,
            related_scope=related_scope,
            html_source=html_source,
            artifacts=artifacts,
            occurrences=occurrences,
            mime_images=mime_images,
            reference_budget=MAX_EMAIL_MEDIA_REFERENCES - reference_count,
        )

    return EmailMediaResolution(
        artifacts=tuple(artifacts.values()),
        occurrences=tuple(occurrences),
    )


def _collect_message_parts(
    part: Message,
    *,
    path: str,
    related_scope: str | None,
    artifacts: dict[str, EmailMediaArtifact],
    occurrences: list[EmailMediaOccurrence],
    mime_images: list[_MimeImagePart],
    html_parts: list[tuple[str, str | None, str]],
) -> None:
    current_scope = (
        path if part.get_content_type() == "multipart/related" else related_scope
    )
    children = _message_children(part)
    if children:
        for index, child in enumerate(children):
            _collect_message_parts(
                child,
                path=f"{path}.{index}",
                related_scope=current_scope,
                artifacts=artifacts,
                occurrences=occurrences,
                mime_images=mime_images,
                html_parts=html_parts,
            )
        return

    content_type = _normalize_content_type(part.get_content_type())
    if content_type == "text/html":
        html_source = _decode_text_part(part)
        if len(html_source) > MAX_EMAIL_MEDIA_HTML_CHARS:
            raise ValueError("email_media_html_size_limit_exceeded")
        html_parts.append((path, current_scope, html_source))
        return

    if part.get_content_maintype().casefold() != "image":
        return

    raw_payload = part.get_payload(decode=True)
    payload = raw_payload if isinstance(raw_payload, bytes) else b""
    artifact = _build_artifact(content_type, payload)
    artifact = _store_artifact(artifacts, artifact)
    content_id = _normalize_content_id(part.get("Content-ID"))
    mime_images.append(
        _MimeImagePart(
            path=path,
            related_scope=current_scope,
            content_id=content_id,
            artifact_id=artifact.artifact_id,
            llm_safe=artifact.llm_safe,
        )
    )
    _append_occurrence(
        occurrences,
        EmailMediaOccurrence(
            occurrence_kind="mime_part",
            source_path=path,
            source_start=None,
            source_end=None,
            raw_reference=None,
            normalized_reference=None,
            content_id=content_id,
            artifact_id=artifact.artifact_id,
            resolution_status="resolved" if artifact.llm_safe else "unsafe_media",
            reason_code=artifact.reason_code,
        ),
    )


def _resolve_html_references(
    *,
    html_path: str,
    related_scope: str | None,
    html_source: str,
    artifacts: dict[str, EmailMediaArtifact],
    occurrences: list[EmailMediaOccurrence],
    mime_images: list[_MimeImagePart],
    reference_budget: int,
) -> int:
    parser = _ImageSourceParser(html_source)
    parser.feed(html_source)
    parser.close()
    if len(parser.references) > reference_budget:
        raise ValueError("email_media_reference_limit_exceeded")

    for raw_reference, source_start, source_end in parser.references:
        normalized_reference = html.unescape(raw_reference).strip()
        lowered_reference = normalized_reference.casefold()
        if lowered_reference.startswith("cid:"):
            occurrence = _resolve_cid_reference(
                html_path=html_path,
                related_scope=related_scope,
                raw_reference=raw_reference,
                normalized_reference=normalized_reference,
                source_start=source_start,
                source_end=source_end,
                mime_images=mime_images,
            )
        elif lowered_reference.startswith("data:"):
            occurrence = _resolve_data_reference(
                html_path=html_path,
                raw_reference=raw_reference,
                normalized_reference=normalized_reference,
                source_start=source_start,
                source_end=source_end,
                artifacts=artifacts,
            )
        elif _is_remote_reference(normalized_reference):
            occurrence = EmailMediaOccurrence(
                occurrence_kind="html_remote",
                source_path=html_path,
                source_start=source_start,
                source_end=source_end,
                raw_reference=raw_reference,
                normalized_reference=normalized_reference,
                content_id=None,
                artifact_id=None,
                resolution_status="remote_blocked",
                reason_code="remote_fetch_disabled",
            )
        else:
            occurrence = EmailMediaOccurrence(
                occurrence_kind="html_external",
                source_path=html_path,
                source_start=source_start,
                source_end=source_end,
                raw_reference=raw_reference,
                normalized_reference=normalized_reference,
                content_id=None,
                artifact_id=None,
                resolution_status="unresolved",
                reason_code="unsupported_image_reference",
            )
        _append_occurrence(occurrences, occurrence)
    return len(parser.references)


def _resolve_cid_reference(
    *,
    html_path: str,
    related_scope: str | None,
    raw_reference: str,
    normalized_reference: str,
    source_start: int,
    source_end: int,
    mime_images: list[_MimeImagePart],
) -> EmailMediaOccurrence:
    cid_value = _normalize_cid_url(normalized_reference)
    if cid_value is None:
        return _reference_occurrence(
            "html_cid",
            html_path,
            source_start,
            source_end,
            raw_reference,
            normalized_reference,
            None,
            None,
            "unresolved",
            "invalid_cid_reference",
        )
    if related_scope is None:
        return _reference_occurrence(
            "html_cid",
            html_path,
            source_start,
            source_end,
            raw_reference,
            normalized_reference,
            cid_value,
            None,
            "unresolved",
            "cid_outside_multipart_related",
        )

    candidates = [
        image
        for image in mime_images
        if image.related_scope == related_scope and image.content_id == cid_value
    ]
    if not candidates:
        return _reference_occurrence(
            "html_cid",
            html_path,
            source_start,
            source_end,
            raw_reference,
            normalized_reference,
            cid_value,
            None,
            "unresolved",
            "cid_target_missing",
        )
    if len(candidates) != 1:
        return _reference_occurrence(
            "html_cid",
            html_path,
            source_start,
            source_end,
            raw_reference,
            normalized_reference,
            cid_value,
            None,
            "review_required",
            "cid_target_ambiguous",
        )

    candidate = candidates[0]
    return _reference_occurrence(
        "html_cid",
        html_path,
        source_start,
        source_end,
        raw_reference,
        normalized_reference,
        cid_value,
        candidate.artifact_id,
        "resolved" if candidate.llm_safe else "unsafe_media",
        "cid_target_resolved" if candidate.llm_safe else "cid_target_not_llm_safe",
    )


def _resolve_data_reference(
    *,
    html_path: str,
    raw_reference: str,
    normalized_reference: str,
    source_start: int,
    source_end: int,
    artifacts: dict[str, EmailMediaArtifact],
) -> EmailMediaOccurrence:
    try:
        content_type, payload = _decode_data_image(normalized_reference)
    except ValueError as exc:
        return _reference_occurrence(
            "html_data",
            html_path,
            source_start,
            source_end,
            raw_reference,
            normalized_reference,
            None,
            None,
            "unresolved",
            str(exc),
        )
    artifact = _store_artifact(artifacts, _build_artifact(content_type, payload))
    return _reference_occurrence(
        "html_data",
        html_path,
        source_start,
        source_end,
        raw_reference,
        normalized_reference,
        None,
        artifact.artifact_id,
        "resolved" if artifact.llm_safe else "unsafe_media",
        "data_image_resolved" if artifact.llm_safe else artifact.reason_code,
    )


def _reference_occurrence(
    occurrence_kind: str,
    source_path: str,
    source_start: int,
    source_end: int,
    raw_reference: str,
    normalized_reference: str,
    content_id: str | None,
    artifact_id: str | None,
    resolution_status: str,
    reason_code: str,
) -> EmailMediaOccurrence:
    return EmailMediaOccurrence(
        occurrence_kind=occurrence_kind,
        source_path=source_path,
        source_start=source_start,
        source_end=source_end,
        raw_reference=raw_reference,
        normalized_reference=normalized_reference,
        content_id=content_id,
        artifact_id=artifact_id,
        resolution_status=resolution_status,
        reason_code=reason_code,
    )


def _append_occurrence(
    occurrences: list[EmailMediaOccurrence], occurrence: EmailMediaOccurrence
) -> None:
    """Append one occurrence while enforcing the per-message provenance bound."""
    if len(occurrences) >= MAX_EMAIL_MEDIA_OCCURRENCES:
        raise ValueError("email_media_occurrence_limit_exceeded")
    occurrences.append(occurrence)


def _build_artifact(content_type: str, payload: bytes) -> EmailMediaArtifact:
    normalized_type = _normalize_content_type(content_type)
    content_sha256 = hashlib.sha256(payload).hexdigest()
    artifact_id = f"sha256:{content_sha256}"
    if len(payload) > MAX_EMAIL_MEDIA_IMAGE_BYTES:
        return EmailMediaArtifact(
            artifact_id,
            content_sha256,
            normalized_type,
            len(payload),
            b"",
            False,
            "unsupported_media",
            "image_size_limit_exceeded",
        )
    inferred_type = _infer_image_content_type(payload)
    if normalized_type not in _SUPPORTED_IMAGE_TYPES:
        return EmailMediaArtifact(
            artifact_id,
            content_sha256,
            normalized_type,
            len(payload),
            b"",
            False,
            "unsupported_media",
            "unsupported_image_content_type",
        )
    if inferred_type != normalized_type:
        return EmailMediaArtifact(
            artifact_id,
            content_sha256,
            normalized_type,
            len(payload),
            b"",
            False,
            "unsupported_media",
            "image_content_type_mismatch",
        )
    dimensions = _image_dimensions(normalized_type, payload)
    visual_classification = (
        "tracking_candidate" if dimensions == (1, 1) else "unclassified"
    )
    return EmailMediaArtifact(
        artifact_id,
        content_sha256,
        normalized_type,
        len(payload),
        payload,
        True,
        visual_classification,
        "llm_safe_image",
    )


def _store_artifact(
    artifacts: dict[str, EmailMediaArtifact], artifact: EmailMediaArtifact
) -> EmailMediaArtifact:
    existing = artifacts.get(artifact.artifact_id)
    if existing is not None:
        return existing
    if len(artifacts) >= MAX_EMAIL_MEDIA_ARTIFACTS:
        raise ValueError("email_media_artifact_limit_exceeded")
    artifacts[artifact.artifact_id] = artifact
    return artifact


def _message_children(part: Message) -> list[Message]:
    payload = part.get_payload()
    if not part.is_multipart() or not isinstance(payload, list):
        return []
    return [child for child in payload if isinstance(child, Message)]


def _decode_text_part(part: Message) -> str:
    try:
        content = part.get_content()
    except (LookupError, TypeError, ValueError):
        content = None
    if isinstance(content, str):
        return content
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _decode_data_image(reference: str) -> tuple[str, bytes]:
    if not reference.casefold().startswith("data:") or "," not in reference:
        raise ValueError("invalid_data_image")
    metadata, encoded_payload = reference[5:].split(",", 1)
    metadata_parts = metadata.split(";") if metadata else []
    content_type = _normalize_content_type(metadata_parts[0] if metadata_parts else "")
    parameters = [item.casefold() for item in metadata_parts[1:]]
    if content_type not in _SUPPORTED_IMAGE_TYPES:
        raise ValueError("unsupported_data_image_content_type")
    if "base64" not in parameters:
        raise ValueError("unsupported_data_image_encoding")
    if len(encoded_payload) > ((MAX_EMAIL_MEDIA_IMAGE_BYTES * 4) // 3) + 16:
        raise ValueError("data_image_size_limit_exceeded")
    try:
        encoded_bytes = urllib.parse.unquote_to_bytes(encoded_payload)
        payload = base64.b64decode(encoded_bytes, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid_data_image_base64") from exc
    if len(payload) > MAX_EMAIL_MEDIA_IMAGE_BYTES:
        raise ValueError("data_image_size_limit_exceeded")
    return content_type, payload


def _normalize_cid_url(reference: str) -> str | None:
    if not reference.casefold().startswith("cid:"):
        return None
    encoded = reference[4:]
    try:
        decoded = urllib.parse.unquote(encoded, errors="strict")
    except UnicodeDecodeError:
        return None
    if not decoded or _CONTROL_CHARACTER_RE.search(decoded) or any(
        character.isspace() for character in decoded
    ):
        return None
    return decoded


def _normalize_content_id(value: object) -> str | None:
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
    normalized = (value or "").split(";", 1)[0].strip().casefold()
    return _IMAGE_TYPE_ALIASES.get(normalized, normalized)


def _infer_image_content_type(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return None


def _image_dimensions(content_type: str, payload: bytes) -> tuple[int, int] | None:
    if content_type == "image/png" and len(payload) >= 24:
        return (
            int.from_bytes(payload[16:20], "big"),
            int.from_bytes(payload[20:24], "big"),
        )
    if content_type == "image/gif" and len(payload) >= 10:
        return (
            int.from_bytes(payload[6:8], "little"),
            int.from_bytes(payload[8:10], "little"),
        )
    return None


def _is_remote_reference(reference: str) -> bool:
    try:
        scheme = urllib.parse.urlsplit(reference).scheme.casefold()
    except ValueError:
        return False
    return scheme in {"http", "https"}


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for match in re.finditer("\n", source):
        offsets.append(match.end())
    return offsets
