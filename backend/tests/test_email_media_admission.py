"""Acceptance tests for #1350 Slice 3 email inline-media admission."""

from __future__ import annotations

from pathlib import Path

from services.email_media_admission import admit_email_inline_media

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "email_media_admission"


def _fixture_bytes(file_name: str) -> bytes:
    """Read one synthetic RFC 5322 fixture as raw message bytes."""
    return (FIXTURE_DIRECTORY / file_name).read_bytes()


def test_cid_related_document_image_resolves_with_hash_provenance() -> None:
    """A cid: reference inside multipart/related admits the local PNG as document evidence."""
    result = admit_email_inline_media(_fixture_bytes("cid_related_document_image.eml"))

    assert result.remote_fetch_policy == "disabled"
    assert len(result.cid_references) == 1
    cid_reference = result.cid_references[0]
    assert cid_reference.error_code is None
    assert cid_reference.content_id == "chart@naruon.test"
    assert cid_reference.media_classification == "document_image"
    assert cid_reference.evidence_boundary == "known"
    assert cid_reference.content_sha256 is not None
    assert len(cid_reference.content_sha256) == 64

    assert len(result.inline_images) == 1
    admitted_image = result.inline_images[0]
    assert admitted_image.source_part_index >= 0
    assert admitted_image.content_id == "chart@naruon.test"
    assert admitted_image.media_classification == "document_image"
    assert admitted_image.evidence_boundary == "known"
    assert admitted_image.error_code is None
    assert admitted_image.content_sha256 == cid_reference.content_sha256
    assert admitted_image.source_part_index == cid_reference.source_part_index
    assert admitted_image.pixel_width == 64
    assert admitted_image.pixel_height == 48


def test_unresolved_cid_fails_closed_and_is_not_document_evidence() -> None:
    """A missing cid: target fails closed with a stable error_code and is not admitted."""
    result = admit_email_inline_media(_fixture_bytes("unresolved_cid.eml"))

    assert result.remote_fetch_policy == "disabled"
    assert len(result.cid_references) == 1
    cid_reference = result.cid_references[0]
    assert cid_reference.content_id == "missing@naruon.test"
    assert cid_reference.error_code == "unresolved_cid_reference"
    assert cid_reference.media_classification is None
    assert cid_reference.content_sha256 is None
    assert cid_reference.source_part_index is None
    assert result.inline_images == ()


def test_tracking_pixel_is_not_document_evidence() -> None:
    """A 1x1 GIF with a tracker Content-Location is classified, not sent as a document."""
    result = admit_email_inline_media(_fixture_bytes("tracking_pixel_1x1.eml"))

    assert result.remote_fetch_policy == "disabled"
    assert len(result.inline_images) == 1
    tracking_pixel = result.inline_images[0]
    assert tracking_pixel.media_classification == "tracking_pixel"
    assert tracking_pixel.evidence_boundary == "known"
    assert tracking_pixel.pixel_width == 1
    assert tracking_pixel.pixel_height == 1
    assert tracking_pixel.declared_content_type == "image/gif"
    assert tracking_pixel.content_location is not None
    assert "list-manage.com" in tracking_pixel.content_location
    assert tracking_pixel.error_code is None
    assert all(
        image.media_classification != "document_image"
        for image in result.inline_images
    )

    assert len(result.cid_references) == 1
    cid_reference = result.cid_references[0]
    assert cid_reference.media_classification == "tracking_pixel"
    assert cid_reference.error_code is None
    assert cid_reference.content_sha256 == tracking_pixel.content_sha256


def test_repeated_identical_base64_parts_share_the_same_hash() -> None:
    """Identical decoded source bytes keep one SHA-256 across distinct part positions."""
    result = admit_email_inline_media(_fixture_bytes("repeated_identical_base64.eml"))

    assert len(result.inline_images) == 2
    first_image, second_image = result.inline_images
    assert first_image.content_sha256 == second_image.content_sha256
    assert first_image.source_part_index != second_image.source_part_index
    assert {first_image.content_id, second_image.content_id} == {
        "scan-one@naruon.test",
        "scan-two@naruon.test",
    }
    assert first_image.media_classification == "document_image"
    assert second_image.media_classification == "document_image"
