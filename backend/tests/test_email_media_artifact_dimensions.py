"""Acceptance tests for intrinsic image dimensions in normalized email media."""

from __future__ import annotations

import base64

from services import email_media_resolution as media


def _png(width: int, height: int) -> bytes:
    """Build the bounded PNG header shape used by the deterministic resolver."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"payload"
    )


def _gif(width: int, height: int) -> bytes:
    """Build the bounded GIF logical-screen header used by the resolver."""
    return (
        b"GIF89a"
        + width.to_bytes(2, "little")
        + height.to_bytes(2, "little")
        + b"payload"
    )


def _html_data_message(content_type: str, payload: bytes) -> bytes:
    """Return one HTML message containing a local base64 data-image occurrence."""
    encoded = base64.b64encode(payload).decode("ascii")
    html = f'<img src="data:{content_type};base64,{encoded}">'
    return (
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Transfer-Encoding: 8bit\r\n\r\n"
        + html.encode("utf-8")
    )


def test_normalized_png_exposes_intrinsic_pixel_dimensions() -> None:
    """A local PNG artifact exposes header-derived width and height for later triage."""
    result = media.resolve_email_media(
        _html_data_message("image/png", _png(width=320, height=180))
    )

    artifact = result.artifacts[0]
    assert artifact.llm_safe is True
    assert artifact.pixel_width == 320
    assert artifact.pixel_height == 180


def test_normalized_gif_exposes_intrinsic_pixel_dimensions() -> None:
    """A local GIF artifact exposes its logical-screen dimensions without decoding pixels."""
    result = media.resolve_email_media(
        _html_data_message("image/gif", _gif(width=48, height=16))
    )

    artifact = result.artifacts[0]
    assert artifact.llm_safe is True
    assert artifact.pixel_width == 48
    assert artifact.pixel_height == 16


def test_supported_format_without_bounded_dimension_parser_stays_explicit() -> None:
    """Supported payloads without deterministic dimension parsing use explicit unknowns."""
    jpeg = b"\xff\xd8\xff" + b"jpeg-data"
    result = media.resolve_email_media(_html_data_message("image/jpeg", jpeg))

    artifact = result.artifacts[0]
    assert artifact.llm_safe is True
    assert artifact.pixel_width is None
    assert artifact.pixel_height is None
