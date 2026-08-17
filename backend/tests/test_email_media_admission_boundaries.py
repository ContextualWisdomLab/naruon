"""Boundary and helper coverage for Slice 3 email media admission."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path

import pytest

from services import email_media_admission as admission


def _png_header(width: int, height: int) -> bytes:
    """Return a signature-bearing PNG whose IHDR carries the given size."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"payload"
    )


def _gif_header(width: int, height: int) -> bytes:
    """Return a GIF89a logical-screen header with the given size."""
    return (
        b"GIF89a"
        + width.to_bytes(2, "little")
        + height.to_bytes(2, "little")
        + b"payload"
    )


def _related_message(
    html_body: str,
    image_parts: list[tuple[str, str, bytes, str | None]],
) -> bytes:
    """Build a multipart/related message for helper-level admission cases."""
    raw = (
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/related; boundary="rel"; type="text/html"\r\n'
        "\r\n"
        "--rel\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"{html_body}\r\n"
    ).encode("utf-8")
    for content_id, content_type, payload, content_location in image_parts:
        headers = (
            f"--rel\r\nContent-Type: {content_type}\r\n"
            f"Content-ID: <{content_id}>\r\n"
        )
        if content_location is not None:
            headers += f"Content-Location: {content_location}\r\n"
        raw += (
            headers.encode("ascii")
            + b"Content-Transfer-Encoding: base64\r\n\r\n"
            + base64.b64encode(payload)
            + b"\r\n"
        )
    return raw + b"--rel--\r\n"


def _html_only_message(html_body: str) -> bytes:
    """Return a single-part HTML message with no related image parts."""
    return (
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"{html_body}"
    ).encode("utf-8")


def test_raw_message_must_be_bytes() -> None:
    """Reject non-bytes input before any MIME walk."""
    with pytest.raises(TypeError, match="raw_message must be bytes"):
        admission.admit_email_inline_media("not-bytes")  # type: ignore[arg-type]


def test_unsupported_and_mismatched_images_are_not_document_evidence() -> None:
    """SVG and signature-mismatched parts stay in the unsupported closed set."""
    result = admission.admit_email_inline_media(
        _related_message(
            "<p>images</p>",
            [
                ("vector@naruon.test", "image/svg+xml", b"<svg></svg>", None),
                ("mismatch@naruon.test", "image/png", _gif_header(8, 8), None),
            ],
        )
    )

    assert {image.media_classification for image in result.inline_images} == {
        admission.UNSUPPORTED_MEDIA_CLASSIFICATION
    }
    assert all(
        image.evidence_boundary == admission.KNOWN_EVIDENCE_BOUNDARY
        for image in result.inline_images
    )
    assert all(image.pixel_width is None for image in result.inline_images)


def test_relative_html_image_is_ignored_for_admission() -> None:
    """Non-cid local file references are not treated as document evidence."""
    result = admission.admit_email_inline_media(
        _html_only_message('<img src="images/chart.png">')
    )
    assert result.inline_images == ()
    assert result.cid_references == ()


def test_remote_html_images_are_not_fetched_or_admitted() -> None:
    """HTTP(S) img src values stay outside admission and never become documents."""
    result = admission.admit_email_inline_media(
        _html_only_message(
            '<img src="https://tracker.example/pixel.gif">'
            '<img src="http://ads.example/open.gif">'
        )
    )

    assert result.remote_fetch_policy == admission.REMOTE_FETCH_POLICY
    assert result.inline_images == ()
    assert result.cid_references == ()


def test_cid_outside_related_and_invalid_cid_fail_closed() -> None:
    """CID without a related scope, or a malformed cid: URL, is unresolved."""
    outside = admission.admit_email_inline_media(
        _html_only_message('<img src="cid:chart@naruon.test">')
    )
    assert outside.cid_references[0].error_code == (
        admission.UNRESOLVED_CID_ERROR_CODE
    )
    assert outside.cid_references[0].media_classification is None

    invalid = admission.admit_email_inline_media(
        _html_only_message('<img src="cid:">' '<img src="cid:bad%0Aid">')
    )
    assert {item.error_code for item in invalid.cid_references} == {
        admission.UNRESOLVED_CID_ERROR_CODE
    }


def test_ambiguous_content_id_fails_closed() -> None:
    """Duplicate Content-ID values in one related scope are not document evidence."""
    result = admission.admit_email_inline_media(
        _related_message(
            '<img src="cid:dup@naruon.test">',
            [
                ("dup@naruon.test", "image/png", _png_header(16, 16), None),
                ("dup@naruon.test", "image/gif", _gif_header(16, 16), None),
            ],
        )
    )
    cid_reference = result.cid_references[0]
    assert cid_reference.error_code == admission.UNRESOLVED_CID_ERROR_CODE
    assert cid_reference.content_sha256 is None


def test_percent_encoded_cid_and_unquoted_src_resolve() -> None:
    """RFC 2392 percent-decoding and unquoted src values still bind uniquely."""
    result = admission.admit_email_inline_media(
        _related_message(
            "<img src=cid:chart%40naruon.test>",
            [("chart@naruon.test", "image/png", _png_header(20, 10), None)],
        )
    )
    assert result.cid_references[0].error_code is None
    assert result.cid_references[0].content_id == "chart@naruon.test"
    assert result.inline_images[0].media_classification == (
        admission.DOCUMENT_IMAGE_CLASSIFICATION
    )


def test_jpeg_without_header_parser_is_document_image_with_unknown_boundary() -> None:
    """Supported JPEG bytes without a local size parser stay unknown, not tracking."""
    jpeg_payload = b"\xff\xd8\xff" + b"jpeg-data"
    result = admission.admit_email_inline_media(
        _related_message(
            "<p>scan</p>",
            [("scan@naruon.test", "image/jpg", jpeg_payload, None)],
        )
    )
    image = result.inline_images[0]
    assert image.declared_content_type == "image/jpeg"
    assert image.media_classification == admission.DOCUMENT_IMAGE_CLASSIFICATION
    assert image.evidence_boundary == admission.UNKNOWN_EVIDENCE_BOUNDARY
    assert image.pixel_width is None
    assert image.pixel_height is None


def test_tracker_content_location_classifies_without_downloading() -> None:
    """A larger GIF with a tracker Content-Location is still a tracking pixel."""
    result = admission.admit_email_inline_media(
        _related_message(
            "<p>ad</p>",
            [
                (
                    "ad@naruon.test",
                    "image/gif",
                    _gif_header(32, 32),
                    "https://click.list-manage.com/track/open.php?u=x",
                )
            ],
        )
    )
    image = result.inline_images[0]
    assert image.media_classification == admission.TRACKING_PIXEL_CLASSIFICATION
    assert image.evidence_boundary == admission.KNOWN_EVIDENCE_BOUNDARY
    assert image.pixel_width == 32


def test_tiny_gif_without_dimensions_uses_tracker_content_type() -> None:
    """A typical tracker GIF with no parseable size is not document evidence."""
    tiny_gif = b"GIF89a" + b"x"
    result = admission.admit_email_inline_media(
        _related_message(
            "<p>beacon</p>",
            [("beacon@naruon.test", "image/gif", tiny_gif, None)],
        )
    )
    image = result.inline_images[0]
    assert image.media_classification == admission.TRACKING_PIXEL_CLASSIFICATION
    assert image.pixel_width is None


def test_tracker_path_marker_and_host_suffix_helpers() -> None:
    """Already-present Content-Location values match host suffixes or path markers."""
    assert admission._content_location_matches_tracker(None) is False
    assert (
        admission._content_location_matches_tracker(
            "https://pixel.doubleclick.net/open.gif"
        )
        is True
    )
    assert (
        admission._content_location_matches_tracker(
            "https://cdn.example.test/pixel.gif"
        )
        is True
    )
    assert (
        admission._content_location_matches_tracker("https://cdn.example.test/logo.png")
        is False
    )
    assert admission._content_location_matches_tracker("http://[broken") is False
    assert admission._content_location_matches_tracker("/open.php") is True
    assert admission._content_location_matches_tracker("https://list-manage.com/x") is True


def test_remote_reference_helper_and_invalid_url() -> None:
    """Only http(s) schemes are remote; broken brackets stay non-remote."""
    assert admission._is_remote_reference("https://example.test/a.png") is True
    assert admission._is_remote_reference("cid:x@naruon.test") is False
    assert admission._is_remote_reference("http://[broken") is False


def test_content_helpers_cover_empty_and_unknown_inputs() -> None:
    """Normalizers reject empty, control, and whitespace identities."""
    assert admission._normalize_content_id(None) is None
    assert admission._normalize_content_id(" <x@naruon.test> ") == "x@naruon.test"
    assert admission._normalize_content_id("") is None
    assert admission._normalize_content_id("<bad id@naruon.test>") is None
    assert admission._normalize_content_id("<bad\x01id>") is None
    assert admission._normalize_content_type("") == ""
    assert admission._normalize_content_type("IMAGE/JPG; name=x") == "image/jpeg"
    assert admission._header_text(None) is None
    assert admission._header_text("  ") is None
    assert admission._header_text(" https://x.test ") == "https://x.test"
    assert admission._infer_image_content_type(b"not-image") is None
    assert admission._infer_image_content_type(
        b"RIFF\x08\x00\x00\x00WEBPdata"
    ) == "image/webp"
    assert admission._infer_image_content_type(b"GIF87a....") == "image/gif"
    assert admission._pixel_dimensions_from_header(
        "image/gif", b"GIF87a" + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
    ) == (1, 1)
    assert admission._pixel_dimensions_from_header("image/jpeg", b"jpeg") is None
    assert admission._pixel_dimensions_from_header("image/png", b"short") is None
    assert admission._pixel_dimensions_from_header("image/gif", b"GIF") is None
    assert admission._normalize_cid_url("https://example.test") is None
    assert admission._normalize_cid_url("cid:%FF") is None
    assert admission._normalize_cid_url("cid:has space@naruon.test") is None


def test_decode_text_part_and_message_children_fallbacks() -> None:
    """Text decode and multipart walking stay deterministic on odd payloads."""
    unknown_charset = EmailMessage()
    unknown_charset.set_content("한글", charset="utf-8")
    unknown_charset.set_param("charset", "not-a-real-charset")
    assert "한글" in admission._decode_text_part(unknown_charset)

    empty_part = EmailMessage()
    empty_part.set_payload(None)
    assert admission._decode_text_part(empty_part) == ""

    string_part = EmailMessage()
    string_part.set_payload("direct")
    assert admission._decode_text_part(string_part) == "direct"

    mixed = EmailMessage()
    mixed.set_content("plain")
    assert admission._message_children(mixed) == []

    class _NonMessageMultipart:
        """Duck-typed multipart whose payload list is not MIME children."""

        def is_multipart(self) -> bool:
            return True

        def get_payload(self) -> list[str]:
            return ["not-a-message"]

    assert admission._message_children(_NonMessageMultipart()) == []  # type: ignore[arg-type]


def test_non_image_parts_and_non_img_tags_are_ignored() -> None:
    """PDF parts and non-img tags do not create inline image admissions."""
    raw = (
        b"MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=m\r\n\r\n"
        b"--m\r\nContent-Type: application/pdf\r\nContent-ID: <doc@naruon.test>\r\n\r\n"
        b"%PDF-1.7\r\n--m\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b'<a src="https://example.test/a">x</a><img alt="none">\r\n--m--\r\n'
    )
    result = admission.admit_email_inline_media(raw)
    assert result.inline_images == ()
    assert result.cid_references == ()


def test_quoted_img_src_and_webp_document_image() -> None:
    """Single-quoted src and WebP signatures admit as document images."""
    webp_payload = b"RIFF\x08\x00\x00\x00WEBPdata"
    result = admission.admit_email_inline_media(
        _related_message(
            "<img src='cid:shot@naruon.test'>",
            [("shot@naruon.test", "image/webp", webp_payload, None)],
        )
    )
    assert result.cid_references[0].error_code is None
    assert result.inline_images[0].media_classification == (
        admission.DOCUMENT_IMAGE_CLASSIFICATION
    )
    assert result.inline_images[0].evidence_boundary == (
        admission.UNKNOWN_EVIDENCE_BOUNDARY
    )


def test_admission_module_has_no_network_client() -> None:
    """The admission module must not grow a fetch path in this slice."""
    source = admission.__file__
    assert source is not None
    module_text = Path(source).read_text(encoding="utf-8")
    assert "httpx" not in module_text
    assert "urllib.request" not in module_text
    assert "urlopen" not in module_text
    assert "socket" not in module_text
