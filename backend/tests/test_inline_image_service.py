"""Tests for source-linked inline HTML image evidence."""

import base64
import hashlib
import struct

import pytest

from services.inline_image_service import (
    InlineImageSource,
    extract_inline_image_sources,
    redact_inline_image_payloads,
)


def _png_fixture(width: int = 320, height: int = 200) -> bytes:
    """Build a header-only PNG fixture without a real image dataset."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
    )


def _data_uri(payload: bytes, media_type: str = "image/png") -> str:
    """Encode a synthetic image as an HTML data URL."""
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def test_inline_image_records_dom_location_and_bounded_header_facts():
    payload = _png_fixture()
    sources = extract_inline_image_sources(
        f"<html><body><p>Intro</p><div><img src='{_data_uri(payload)}'></div></body></html>"
    )

    assert len(sources) == 1
    source = sources[0]
    assert source.source_locator_type == "html_dom_path"
    assert source.source_locator_value == "/html[1]/body[1]/div[1]/img[1]"
    assert source.source_ordinal == 1
    assert source.media_type == "image/png"
    assert source.byte_count == len(payload)
    assert source.content_digest == hashlib.sha256(payload).hexdigest()
    assert source.detected_format == "png"
    assert (source.pixel_width, source.pixel_height) == (320, 200)
    assert source.is_animated is False
    assert source.parse_status == "metadata_ready"
    assert source.parse_error_code is None
    assert "Inline image evidence" in source.searchable_text
    assert base64.b64encode(payload).decode("ascii") not in source.searchable_text


def test_inline_image_paths_are_stable_for_repeated_siblings():
    payload = _data_uri(_png_fixture(2, 3))
    sources = extract_inline_image_sources(
        f"<section><img src='{payload}'><img src='{payload}'></section>"
    )

    assert [source.source_ordinal for source in sources] == [1, 2]
    assert [source.source_locator_value for source in sources] == [
        "/section[1]/img[1]",
        "/section[1]/img[2]",
    ]


def test_inline_image_parser_handles_self_closing_and_unmatched_tags():
    source = extract_inline_image_sources(
        f"</orphan><img src='{_data_uri(_png_fixture())}' />"
    )[0]

    assert source.source_locator_value == "/img[1]"


def test_inline_image_searchable_text_omits_optional_facts_when_unavailable():
    source = InlineImageSource(
        source_locator_type="html_dom_path",
        source_locator_value="/html[1]/img[1]",
        source_ordinal=1,
        media_type="image/png",
        byte_count=None,
        content_digest=None,
        detected_format=None,
        pixel_width=None,
        pixel_height=None,
        is_animated=None,
        parse_status="inline_image_parse_failed",
        parse_error_code="invalid_image_payload",
    )

    searchable_text = source.searchable_text

    assert "bytes=" not in searchable_text
    assert "digest=" not in searchable_text
    assert "format=" not in searchable_text
    assert "width=" not in searchable_text
    assert "height=" not in searchable_text
    assert "animated=" not in searchable_text
    assert "error=invalid_image_payload" in searchable_text


def test_inline_image_searchable_text_renders_true_animation():
    source = InlineImageSource(
        source_locator_type="html_dom_path",
        source_locator_value="/img[1]",
        source_ordinal=1,
        media_type="image/gif",
        byte_count=12,
        content_digest="digest",
        detected_format="gif",
        pixel_width=2,
        pixel_height=3,
        is_animated=True,
        parse_status="metadata_ready",
        parse_error_code=None,
    )

    assert "animated=yes" in source.searchable_text


@pytest.mark.parametrize(
    ("html", "error_code"),
    [
        ("<img src='data:image/png;base64,not-base64'>", "invalid_base64_payload"),
        ("<img src='data:image/png,plain-text'>", "unsupported_image_encoding"),
        ("<img src='data:image/webp;base64,AAAA'>", "unsupported_image_media_type"),
        ("<img src='data:image/png;base64'>", "malformed_data_uri"),
    ],
)
def test_inline_image_failures_are_explicit_and_do_not_retain_bytes(html, error_code):
    source = extract_inline_image_sources(html)[0]

    assert source.parse_status in {
        "inline_image_parse_failed",
        "inline_image_not_supported",
    }
    assert source.parse_error_code == error_code
    assert source.content_digest is None
    assert source.byte_count is None


def test_non_data_images_are_not_treated_as_inline_base64():
    assert extract_inline_image_sources(
        "<img src='https://example.test/image.png'><img alt='none'>"
    ) == ()


def test_empty_inline_inputs_are_safe():
    assert extract_inline_image_sources(None) == ()
    assert extract_inline_image_sources("") == ()
    assert redact_inline_image_payloads(None) == ""
    assert redact_inline_image_payloads("") == ""


def test_embedding_input_redacts_inline_image_bytes():
    html = '<p>Context</p><img src="data:image/png;base64,secret-bytes"><img src=data:image/png;base64,other-bytes>'

    redacted = redact_inline_image_payloads(html)

    assert "secret-bytes" not in redacted
    assert "other-bytes" not in redacted
    assert "data:image/png" not in redacted
    assert 'src="inline-image://bytes-omitted"' in redacted


def test_inline_image_decodes_percent_escaped_base64_payload():
    payload = _png_fixture(7, 9)
    encoded = base64.b64encode(payload).decode("ascii").replace("+", "%2B")
    source = extract_inline_image_sources(
        f"<img src='data:image/png;base64,{encoded}'>"
    )[0]

    assert source.parse_status == "metadata_ready"
    assert source.pixel_width == 7
    assert source.pixel_height == 9


def test_inline_image_size_limit_is_a_predictable_parse_outcome(monkeypatch):
    import services.inline_image_service as service

    monkeypatch.setattr(service, "MAX_INLINE_IMAGE_ENCODED_CHARS", 3)
    source = extract_inline_image_sources(
        f"<img src='{_data_uri(_png_fixture())}'>"
    )[0]

    assert source.parse_status == "inline_image_size_limit_exceeded"
    assert source.parse_error_code == "inline_image_size_limit_exceeded"
    assert source.content_digest is None


def test_inline_image_decoded_size_limit_is_a_predictable_parse_outcome(monkeypatch):
    import services.inline_image_service as service

    monkeypatch.setattr(service, "MAX_INLINE_IMAGE_BYTES", 1)
    source = extract_inline_image_sources(
        f"<img src='{_data_uri(_png_fixture())}'>"
    )[0]

    assert source.parse_status == "inline_image_size_limit_exceeded"
    assert source.parse_error_code == "inline_image_size_limit_exceeded"


def test_inline_image_invalid_decoded_bytes_are_retained_only_as_digest():
    encoded = base64.b64encode(b"not an image").decode("ascii")
    source = extract_inline_image_sources(
        f"<img src='data:image/png;base64,{encoded}'>"
    )[0]

    assert source.parse_status == "inline_image_parse_failed"
    assert source.parse_error_code == "invalid_image_payload"
    assert source.byte_count == len(b"not an image")
    assert source.content_digest == hashlib.sha256(b"not an image").hexdigest()
