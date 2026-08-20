"""Boundary coverage for Slice 3 email-media resolution wiring."""

from __future__ import annotations

import base64

import pytest

from services import email_media_admission as admission
from services import email_media_resolution as resolution
from services.email_parser import parse_eml_bytes


def _png_header(width: int, height: int) -> bytes:
    """Return a signature-bearing PNG whose IHDR carries the given size."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"payload"
    )


def _related_message(
    html_body: str,
    image_parts: list[tuple[str, str, bytes, str | None, str | None]],
) -> bytes:
    """Build a multipart/related message with optional image filenames."""
    raw = (
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/related; boundary="rel"; type="text/html"\r\n'
        "\r\n"
        "--rel\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"{html_body}\r\n"
    ).encode("utf-8")
    for content_id, content_type, payload, content_location, filename in image_parts:
        headers = (
            f"--rel\r\nContent-Type: {content_type}\r\n"
            f"Content-ID: <{content_id}>\r\n"
        )
        if content_location is not None:
            headers += f"Content-Location: {content_location}\r\n"
        if filename is not None:
            headers += f'Content-Disposition: inline; filename="{filename}"\r\n'
        raw += (
            headers.encode("ascii")
            + b"Content-Transfer-Encoding: base64\r\n\r\n"
            + base64.b64encode(payload)
            + b"\r\n"
        )
    return raw + b"--rel--\r\n"


def test_raw_message_must_be_bytes() -> None:
    """Reject non-bytes input before admission or continuation."""
    with pytest.raises(TypeError, match="raw_message must be bytes"):
        resolution.resolve_email_inline_media("not-bytes")  # type: ignore[arg-type]


def test_unsupported_media_is_quarantined_and_dropped_from_attachments() -> None:
    """SVG and signature-mismatched parts cannot continue as document evidence."""
    raw_message = _related_message(
        '<p>images</p><img src="cid:vector@naruon.test">',
        [
            ("vector@naruon.test", "image/svg+xml", b"<svg></svg>", None, "logo.svg"),
            (
                "mismatch@naruon.test",
                "image/png",
                b"GIF89a" + (8).to_bytes(2, "little") + (8).to_bytes(2, "little"),
                None,
                "mismatch.png",
            ),
        ],
    )

    result = resolution.resolve_email_inline_media(raw_message)
    parsed = parse_eml_bytes(raw_message)

    assert result.document_images == ()
    assert {item.error_code for item in result.quarantined_media} == {
        "unsupported_media"
    }
    assert parsed["attachments"] == []
    assert parsed["inline_media_resolution"].document_images == ()


def test_repeated_document_images_all_continue() -> None:
    """Identical document scans keep distinct part indexes and both continue."""
    payload = _png_header(64, 48)
    raw_message = _related_message(
        "<p>scans</p>",
        [
            ("scan-one@naruon.test", "image/png", payload, None, None),
            ("scan-two@naruon.test", "image/png", payload, None, None),
        ],
    )

    result = resolution.resolve_email_inline_media(raw_message)

    assert result.quarantined_media == ()
    assert len(result.document_images) == 2
    first_image, second_image = result.document_images
    assert first_image.content_sha256 == second_image.content_sha256
    assert first_image.source_part_index != second_image.source_part_index
    assert {first_image.content_id, second_image.content_id} == {
        "scan-one@naruon.test",
        "scan-two@naruon.test",
    }


def test_tracking_pixel_cid_is_not_duplicated_as_unresolved() -> None:
    """A resolved tracker CID is quarantined once as tracking_pixel, not unresolved."""
    raw_message = _related_message(
        '<img src="cid:open-pixel@naruon.test">',
        [
            (
                "open-pixel@naruon.test",
                "image/gif",
                b"GIF89a" + (1).to_bytes(2, "little") + (1).to_bytes(2, "little"),
                "https://click.list-manage.com/track/open.php?u=fixture",
                None,
            )
        ],
    )

    result = resolution.resolve_email_inline_media(raw_message)

    assert result.document_images == ()
    assert [item.error_code for item in result.quarantined_media] == ["tracking_pixel"]


def test_non_image_named_attachments_are_unchanged() -> None:
    """Admission wiring must not drop ordinary non-image filename attachments."""
    raw_message = (
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=mix\r\n\r\n"
        b"--mix\r\nContent-Type: text/plain\r\n\r\nSee attached.\r\n"
        b"--mix\r\nContent-Type: text/plain\r\n"
        b'Content-Disposition: attachment; filename="notes.txt"\r\n\r\n'
        b"hello\r\n--mix--\r\n"
    )

    parsed = parse_eml_bytes(raw_message)

    assert len(parsed["attachments"]) == 1
    assert parsed["attachments"][0]["filename"] == "notes.txt"
    assert parsed["inline_media_resolution"].document_images == ()
    assert parsed["inline_media_resolution"].quarantined_media == ()


def test_resolution_reuses_admission_closed_set_constants() -> None:
    """Wiring error_codes stay the admission closed set, not a new vocabulary."""
    assert resolution.TRACKING_PIXEL_ERROR_CODE == (
        admission.TRACKING_PIXEL_CLASSIFICATION
    )
    assert resolution.UNSUPPORTED_MEDIA_ERROR_CODE == (
        admission.UNSUPPORTED_MEDIA_CLASSIFICATION
    )
    assert resolution.UNRESOLVED_CID_ERROR_CODE == admission.UNRESOLVED_CID_ERROR_CODE
    assert resolution.DOCUMENT_IMAGE_CLASSIFICATION == (
        admission.DOCUMENT_IMAGE_CLASSIFICATION
    )


def test_named_document_image_attachment_is_kept() -> None:
    """A filename-bearing document PNG remains an attachment after admission wiring."""
    payload = _png_header(64, 48)
    raw_message = _related_message(
        '<p>chart</p><img src="cid:chart@naruon.test">',
        [("chart@naruon.test", "image/png", payload, None, "chart.png")],
    )

    parsed = parse_eml_bytes(raw_message)

    assert len(parsed["attachments"]) == 1
    assert parsed["attachments"][0]["filename"] == "chart.png"
    assert parsed["attachments"][0]["parse_status"] == "unsupported_content_type"
    assert len(parsed["inline_media_resolution"].document_images) == 1
    assert (
        parsed["inline_media_resolution"].document_images[0].content_id
        == "chart@naruon.test"
    )


def test_image_bytes_are_document_evidence_matches_hash_or_content_id() -> None:
    """Continuation matching uses exact source bytes or the bound Content-ID."""
    payload = _png_header(64, 48)
    raw_message = _related_message(
        '<img src="cid:chart@naruon.test">',
        [("chart@naruon.test", "image/png", payload, None, None)],
    )
    media_resolution = resolution.resolve_email_inline_media(raw_message)

    assert resolution.image_bytes_are_document_evidence(
        payload_bytes=payload,
        content_id=None,
        media_resolution=media_resolution,
    )
    assert resolution.image_bytes_are_document_evidence(
        payload_bytes=b"different-bytes",
        content_id="chart@naruon.test",
        media_resolution=media_resolution,
    )
    assert not resolution.image_bytes_are_document_evidence(
        payload_bytes=b"different-bytes",
        content_id="other@naruon.test",
        media_resolution=media_resolution,
    )


def test_error_code_helpers_cover_explicit_and_unknown_classifications() -> None:
    """Quarantine helpers keep an explicit error_code and fail closed on unknowns."""
    explicit = admission.InlineImageAdmission(
        source_part_index=0,
        content_id="pixel@naruon.test",
        content_sha256="ab",
        media_classification=admission.TRACKING_PIXEL_CLASSIFICATION,
        evidence_boundary=admission.KNOWN_EVIDENCE_BOUNDARY,
        error_code="tracking_pixel",
        declared_content_type="image/gif",
        content_location=None,
        pixel_width=1,
        pixel_height=1,
    )
    unknown = admission.InlineImageAdmission(
        source_part_index=1,
        content_id=None,
        content_sha256="cd",
        media_classification="unexpected_label",
        evidence_boundary=admission.KNOWN_EVIDENCE_BOUNDARY,
        error_code=None,
        declared_content_type="image/png",
        content_location=None,
        pixel_width=None,
        pixel_height=None,
    )

    assert resolution._error_code_for_image(explicit) == "tracking_pixel"
    assert resolution._error_code_for_image(unknown) == "unsupported_media"
    assert resolution.normalize_image_content_id(" <chart@naruon.test> ") == (
        "chart@naruon.test"
    )
    assert resolution.normalize_image_content_id(None) is None
    missing_code = admission.CidReferenceAdmission(
        raw_reference="cid:missing@naruon.test",
        content_id="missing@naruon.test",
        source_part_index=None,
        content_sha256=None,
        media_classification=None,
        error_code=None,
        evidence_boundary=admission.KNOWN_EVIDENCE_BOUNDARY,
    )
    assert resolution._quarantined_cid_reference(missing_code).error_code == (
        "unresolved_cid_reference"
    )
