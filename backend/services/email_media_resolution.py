"""Continue only admitted document images after local email-media admission.

This module is the #1350 Slice 3 wiring boundary. It calls
``admit_email_inline_media()`` first and drops or quarantines every
non-``document_image`` outcome so later OCR, VLM, or NewsDOM work cannot
treat a tracking pixel, unsupported part, or unresolved CID as document
evidence. When a persist store and message identity are provided, dropped
parts are recorded through ``services.email_media_quarantine``. It does not
fetch remote images, run a model, or copy the #1376 ``EmailMediaArtifact``
pixel contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from services.email_media_admission import (
    DOCUMENT_IMAGE_CLASSIFICATION,
    TRACKING_PIXEL_CLASSIFICATION,
    UNRESOLVED_CID_ERROR_CODE,
    UNSUPPORTED_MEDIA_CLASSIFICATION,
    CidReferenceAdmission,
    EmailMediaAdmissionResult,
    InlineImageAdmission,
    _normalize_content_id,
    admit_email_inline_media,
)
from services.email_media_quarantine import (
    EmailMediaQuarantineStore,
    persist_resolution_if_requested,
)

TRACKING_PIXEL_ERROR_CODE = TRACKING_PIXEL_CLASSIFICATION
UNSUPPORTED_MEDIA_ERROR_CODE = UNSUPPORTED_MEDIA_CLASSIFICATION


@dataclass(frozen=True)
class ContinuedDocumentImage:
    """One admitted local image that may continue as document evidence."""

    source_part_index: int
    content_id: str | None
    content_sha256: str
    media_classification: str
    evidence_boundary: str
    declared_content_type: str


@dataclass(frozen=True)
class QuarantinedInlineMedia:
    """One admission outcome that must not continue as document evidence."""

    source_part_index: int | None
    content_id: str | None
    content_sha256: str | None
    media_classification: str | None
    error_code: str
    evidence_boundary: str | None
    raw_reference: str | None


@dataclass(frozen=True)
class EmailInlineMediaResolution:
    """Admission-gated continuation set for one raw RFC 5322 message."""

    document_images: tuple[ContinuedDocumentImage, ...]
    quarantined_media: tuple[QuarantinedInlineMedia, ...]
    remote_fetch_policy: str


def resolve_email_inline_media(
    raw_message: bytes,
    *,
    message_record_id: int | None = None,
    quarantine_store: EmailMediaQuarantineStore | None = None,
) -> EmailInlineMediaResolution:
    """Admit local inline media, then continue only ``document_image`` results.

    Args:
        raw_message: Complete RFC 5322 message bytes, including MIME headers.
        message_record_id: ``email_records`` primary key when persist is requested.
        quarantine_store: Optional persist store for dropped parts.

    Returns:
        Continued document images plus quarantined non-document outcomes.

    Raises:
        TypeError: If ``raw_message`` is not ``bytes``.
        EmailMediaQuarantinePersistError: If persist was requested and failed.
    """
    admission_result = admit_email_inline_media(raw_message)
    resolution = _resolution_from_admission(admission_result)
    persist_resolution_if_requested(
        media_resolution=resolution,
        message_record_id=message_record_id,
        quarantine_store=quarantine_store,
    )
    return resolution


def normalize_image_content_id(value: object) -> str | None:
    """Normalize a Content-ID header with the admission RFC 2392 rules."""
    return _normalize_content_id(value)


def image_bytes_are_document_evidence(
    *,
    payload_bytes: bytes,
    content_id: str | None,
    media_resolution: EmailInlineMediaResolution,
) -> bool:
    """Return True when this local image may continue as document evidence.

    Matching uses the SHA-256 of the exact decoded source bytes, or the
    Content-ID already bound by admission. Callers must not treat a hash
    miss plus a missing Content-ID as a reason to send bytes to a model.
    """
    content_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    for image in media_resolution.document_images:
        if image.content_sha256 == content_sha256:
            return True
        if content_id is not None and image.content_id == content_id:
            return True
    return False


def _resolution_from_admission(
    admission_result: EmailMediaAdmissionResult,
) -> EmailInlineMediaResolution:
    """Split one admission result into continued images and quarantined media."""
    document_images: list[ContinuedDocumentImage] = []
    quarantined_media: list[QuarantinedInlineMedia] = []
    for image in admission_result.inline_images:
        if image.media_classification == DOCUMENT_IMAGE_CLASSIFICATION:
            document_images.append(_continued_document_image(image))
            continue
        quarantined_media.append(_quarantined_inline_image(image))
    for cid_reference in admission_result.cid_references:
        if cid_reference.error_code == UNRESOLVED_CID_ERROR_CODE:
            quarantined_media.append(_quarantined_cid_reference(cid_reference))
    return EmailInlineMediaResolution(
        document_images=tuple(document_images),
        quarantined_media=tuple(quarantined_media),
        remote_fetch_policy=admission_result.remote_fetch_policy,
    )


def _continued_document_image(
    image: InlineImageAdmission,
) -> ContinuedDocumentImage:
    """Copy provenance for one image that may continue downstream."""
    return ContinuedDocumentImage(
        source_part_index=image.source_part_index,
        content_id=image.content_id,
        content_sha256=image.content_sha256,
        media_classification=image.media_classification,
        evidence_boundary=image.evidence_boundary,
        declared_content_type=image.declared_content_type,
    )


def _quarantined_inline_image(
    image: InlineImageAdmission,
) -> QuarantinedInlineMedia:
    """Quarantine a classified local image that is not document evidence."""
    return QuarantinedInlineMedia(
        source_part_index=image.source_part_index,
        content_id=image.content_id,
        content_sha256=image.content_sha256,
        media_classification=image.media_classification,
        error_code=_error_code_for_image(image),
        evidence_boundary=image.evidence_boundary,
        raw_reference=None,
    )


def _quarantined_cid_reference(
    cid_reference: CidReferenceAdmission,
) -> QuarantinedInlineMedia:
    """Quarantine a CID reference that admission could not bind."""
    return QuarantinedInlineMedia(
        source_part_index=cid_reference.source_part_index,
        content_id=cid_reference.content_id,
        content_sha256=cid_reference.content_sha256,
        media_classification=cid_reference.media_classification,
        error_code=cid_reference.error_code or UNRESOLVED_CID_ERROR_CODE,
        evidence_boundary=cid_reference.evidence_boundary,
        raw_reference=cid_reference.raw_reference,
    )


def _error_code_for_image(image: InlineImageAdmission) -> str:
    """Return a stable quarantine error_code for one non-document image."""
    if image.error_code:
        return image.error_code
    if image.media_classification == TRACKING_PIXEL_CLASSIFICATION:
        return TRACKING_PIXEL_ERROR_CODE
    return UNSUPPORTED_MEDIA_ERROR_CODE
