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
