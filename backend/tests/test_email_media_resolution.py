"""Acceptance tests for Slice 3 admission wiring into local media resolution."""

from __future__ import annotations

import base64
from pathlib import Path

from services.email_media_resolution import resolve_email_inline_media
from services.email_parser import parse_eml_bytes

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "email_media_admission"
TRACKING_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
)


def _fixture_bytes(file_name: str) -> bytes:
    """Read one synthetic RFC 5322 admission fixture as raw message bytes."""
    return (FIXTURE_DIRECTORY / file_name).read_bytes()


def _related_image_message(
    *,
    html_body: str,
    content_id: str,
    content_type: str,
    payload: bytes,
    filename: str | None = None,
    content_location: str | None = None,
) -> bytes:
    """Build a multipart/related message with one inline image part."""
    disposition = "inline"
    if filename is not None:
        disposition = f'inline; filename="{filename}"'
    location_header = (
        f"Content-Location: {content_location}\r\n" if content_location else ""
    )
    return (
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/related; boundary="rel-bound"; type="text/html"\r\n'
        "\r\n"
        "--rel-bound\r\n"
        "Content-Type: text/html; charset=\"utf-8\"\r\n"
        "\r\n"
        f"{html_body}\r\n"
        "--rel-bound\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-ID: <{content_id}>\r\n"
        f"{location_header}"
        f"Content-Disposition: {disposition}\r\n"
        "Content-Transfer-Encoding: base64\r\n"
        "\r\n"
    ).encode("ascii") + base64.b64encode(payload) + b"\r\n--rel-bound--\r\n"


def test_tracking_pixel_does_not_continue_as_document_evidence() -> None:
    """A 1x1 CID tracker is quarantined and is not later OCR/document input."""
    result = resolve_email_inline_media(_fixture_bytes("tracking_pixel_1x1.eml"))

    assert result.document_images == ()
    assert result.remote_fetch_policy == "disabled"
    assert len(result.quarantined_media) == 1
    quarantined = result.quarantined_media[0]
    assert quarantined.error_code == "tracking_pixel"
    assert quarantined.media_classification == "tracking_pixel"
    assert quarantined.content_id == "open-pixel@naruon.test"
    assert quarantined.content_sha256 is not None
    assert not hasattr(quarantined, "payload_bytes")


def test_unresolved_cid_does_not_continue_as_document_evidence() -> None:
    """A missing cid: target is quarantined with the stable unresolved error_code."""
    result = resolve_email_inline_media(_fixture_bytes("unresolved_cid.eml"))

    assert result.document_images == ()
    assert len(result.quarantined_media) == 1
    quarantined = result.quarantined_media[0]
    assert quarantined.error_code == "unresolved_cid_reference"
    assert quarantined.content_id == "missing@naruon.test"
    assert quarantined.content_sha256 is None
    assert quarantined.source_part_index is None


def test_resolving_cid_chart_continues_as_document_image() -> None:
    """A related CID chart is the only admission that may continue downstream."""
    result = resolve_email_inline_media(
        _fixture_bytes("cid_related_document_image.eml")
    )

    assert result.quarantined_media == ()
    assert len(result.document_images) == 1
    continued = result.document_images[0]
    assert continued.media_classification == "document_image"
    assert continued.content_id == "chart@naruon.test"
    assert continued.content_sha256 is not None
    assert len(continued.content_sha256) == 64
    assert continued.source_part_index >= 0
    assert not hasattr(continued, "payload_bytes")


def test_parse_path_drops_filename_tracking_pixel_from_attachments() -> None:
    """The existing parse path must not keep a named 1x1 CID tracker as an attachment."""
    raw_message = _related_image_message(
        html_body='<p>Newsletter</p><img src="cid:open-pixel@naruon.test">',
        content_id="open-pixel@naruon.test",
        content_type="image/gif",
        payload=TRACKING_PIXEL_GIF,
        filename="open.gif",
        content_location="https://click.list-manage.com/track/open.php?u=fixture",
    )

    parsed = parse_eml_bytes(raw_message)

    assert parsed["attachments"] == []
    resolution = parsed["inline_media_resolution"]
    assert resolution.document_images == ()
    assert {item.error_code for item in resolution.quarantined_media} == {
        "tracking_pixel"
    }


def test_parse_path_continues_named_cid_chart_and_keeps_document_attachment() -> None:
    """A named resolving CID chart remains document evidence on the parse path."""
    chart_bytes = _fixture_bytes("cid_related_document_image.eml")
    parsed = parse_eml_bytes(chart_bytes)
    resolution = parsed["inline_media_resolution"]

    assert len(resolution.document_images) == 1
    assert resolution.document_images[0].media_classification == "document_image"
    assert resolution.document_images[0].content_id == "chart@naruon.test"
    assert resolution.quarantined_media == ()


def test_parse_path_quarantines_unresolved_cid_without_document_images() -> None:
    """Unresolved CID stays fail-closed on the parse path and is not document evidence."""
    parsed = parse_eml_bytes(_fixture_bytes("unresolved_cid.eml"))
    resolution = parsed["inline_media_resolution"]

    assert parsed["attachments"] == []
    assert resolution.document_images == ()
    assert {item.error_code for item in resolution.quarantined_media} == {
        "unresolved_cid_reference"
    }
