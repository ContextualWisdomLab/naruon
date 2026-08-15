"""Fallback and helper coverage for deterministic email media resolution."""

from __future__ import annotations

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
