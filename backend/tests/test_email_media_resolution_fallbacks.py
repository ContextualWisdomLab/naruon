"""Fallback and helper coverage for deterministic email media resolution."""

from __future__ import annotations

import base64

import pytest

from services import email_media_resolution as media


class _BrokenTextPart:
    """Small duck-typed MIME part used to exercise decode fallbacks."""

    def __init__(
        self,
        *,
        payload: object,
        charset: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self._payload = payload
        self._charset = charset
        self._error = error

    def get_content(self) -> object:
        if self._error is not None:
            raise self._error
        return self._payload

    def get_payload(self, decode: bool = False) -> object:
        del decode
        return self._payload

    def get_content_charset(self) -> str | None:
        return self._charset


def _png() -> bytes:
    """Return a minimal signature-bearing PNG fixture."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x02\x00\x00\x00\x03payload"
    )


def _multipart_alternative_with_two_html_references() -> bytes:
    """Build two HTML alternatives whose aggregate reference count is two."""
    return (
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/alternative; boundary=alt\r\n\r\n"
        b"--alt\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b'<img src="https://one.example/image.png">\r\n'
        b"--alt\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b'<img src="https://two.example/image.png">\r\n'
        b"--alt--\r\n"
    )


def _related_with_two_identical_images() -> bytes:
    """Build repeated MIME image occurrences that deduplicate to one artifact."""
    encoded = base64.b64encode(_png())
    return (
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/related; boundary=rel\r\n\r\n"
        b"--rel\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>x</p>\r\n"
        b"--rel\r\nContent-Type: image/png\r\nContent-ID: <one@example.test>\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        + encoded
        + b"\r\n--rel\r\nContent-Type: image/png\r\n"
        b"Content-ID: <two@example.test>\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        + encoded
        + b"\r\n--rel--\r\n"
    )


def _related_with_conflicting_content_types(*, safe_first: bool) -> bytes:
    """Build one payload with a valid and a mismatched MIME declaration."""
    encoded = base64.b64encode(_png())
    image_parts = [
        (b"image/png", b"safe@example.test"),
        (b"image/jpeg", b"mismatch@example.test"),
    ]
    if not safe_first:
        image_parts.reverse()

    message_parts = [
        b"MIME-Version: 1.0\r\n",
        b"Content-Type: multipart/related; boundary=rel\r\n\r\n",
        b"--rel\r\nContent-Type: text/html; charset=utf-8\r\n\r\n",
        (
            b'<img src="cid:safe@example.test">'
            b'<img src="cid:mismatch@example.test">\r\n'
        ),
    ]
    for content_type, content_id in image_parts:
        message_parts.extend(
            [
                b"--rel\r\nContent-Type: " + content_type + b"\r\n",
                b"Content-ID: <" + content_id + b">\r\n",
                b"Content-Transfer-Encoding: base64\r\n\r\n",
                encoded,
                b"\r\n",
            ]
        )
    message_parts.append(b"--rel--\r\n")
    return b"".join(message_parts)


def test_decode_text_part_fallbacks_are_deterministic() -> None:
    """Decode bytes safely after content-manager and charset failures."""
    ascii_part = _BrokenTextPart(
        payload=b"hello",
        charset="ascii",
        error=ValueError("broken content manager"),
    )
    assert media._decode_text_part(ascii_part) == "hello"  # type: ignore[arg-type]

    unknown_charset = _BrokenTextPart(
        payload="한글".encode(),
        charset="not-a-real-charset",
        error=LookupError("unknown content manager"),
    )
    assert media._decode_text_part(unknown_charset) == "한글"  # type: ignore[arg-type]

    missing_payload = _BrokenTextPart(
        payload=None,
        error=TypeError("not decodable"),
    )
    assert media._decode_text_part(missing_payload) == ""  # type: ignore[arg-type]

    direct_text = _BrokenTextPart(payload="direct")
    assert media._decode_text_part(direct_text) == "direct"  # type: ignore[arg-type]


def test_cid_normalizer_rejects_wrong_scheme_bad_utf8_and_whitespace() -> None:
    """Reject references that cannot safely identify a MIME Content-ID."""
    assert media._normalize_cid_url("https://example.test") is None
    assert media._normalize_cid_url("cid:%FF") is None
    assert media._normalize_cid_url("cid:has space@example.test") is None


def test_content_id_header_with_internal_whitespace_is_not_linkage_authority() -> None:
    """Reject malformed Content-ID values rather than matching ambiguous text."""
    assert media._normalize_content_id("<bad id@example.test>") is None


def test_reference_limit_is_aggregate_across_all_html_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent multipart messages from multiplying a nominal per-message budget."""
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_REFERENCES", 1)
    with pytest.raises(ValueError, match="email_media_reference_limit_exceeded"):
        media.resolve_email_media(_multipart_alternative_with_two_html_references())


def test_occurrence_limit_bounds_repeated_deduplicated_mime_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound provenance growth even when repeated payloads share one artifact."""
    monkeypatch.setattr(media, "MAX_EMAIL_MEDIA_OCCURRENCES", 1)
    with pytest.raises(ValueError, match="email_media_occurrence_limit_exceeded"):
        media.resolve_email_media(_related_with_two_identical_images())


@pytest.mark.parametrize("safe_first", [True, False])
def test_content_dedupe_never_upgrades_a_mismatched_occurrence(
    safe_first: bool,
) -> None:
    """Keep per-occurrence MIME safety independent of payload deduplication order."""
    resolution = media.resolve_email_media(
        _related_with_conflicting_content_types(safe_first=safe_first)
    )

    assert len(resolution.artifacts) == 1
    artifact = resolution.artifacts[0]
    assert artifact.content_type == "image/png"
    assert artifact.llm_safe is True

    mime_occurrences = {
        occurrence.content_id: occurrence
        for occurrence in resolution.occurrences
        if occurrence.occurrence_kind == "mime_part"
    }
    assert mime_occurrences["safe@example.test"].resolution_status == "resolved"
    assert mime_occurrences["safe@example.test"].reason_code == "llm_safe_image"
    assert (
        mime_occurrences["mismatch@example.test"].resolution_status
        == "unsafe_media"
    )
    assert (
        mime_occurrences["mismatch@example.test"].reason_code
        == "image_content_type_mismatch"
    )

    cid_occurrences = {
        occurrence.content_id: occurrence
        for occurrence in resolution.occurrences
        if occurrence.occurrence_kind == "html_cid"
    }
    assert cid_occurrences["safe@example.test"].resolution_status == "resolved"
    assert (
        cid_occurrences["mismatch@example.test"].resolution_status
        == "unsafe_media"
    )
    assert (
        cid_occurrences["mismatch@example.test"].reason_code
        == "cid_target_not_llm_safe"
    )
