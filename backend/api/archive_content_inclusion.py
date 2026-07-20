"""Authenticated bounded validation for DiskSage archive inclusion evidence."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.archive_content_inclusion import (
    ArchiveContentInclusionValidationResponse,
    DiskSageArchiveContentInclusionEnvelope,
    archive_content_inclusion_validation_response,
)


router = APIRouter(
    prefix="/api/archive-content-inclusion",
    tags=["archive-content-inclusion"],
)

MAX_DISKSAGE_ARCHIVE_CONTENT_INCLUSION_BODY_BYTES = 256 * 1024
ARCHIVE_CONTENT_INCLUSION_TOO_LARGE_ERROR = (
    "disksage_archive_content_inclusion_too_large"
)
ARCHIVE_CONTENT_INCLUSION_INVALID_ERROR = "disksage_archive_content_inclusion_invalid"


@router.post("/validate", response_model=ArchiveContentInclusionValidationResponse)
async def validate_disksage_archive_content_inclusion(
    request: Request,
) -> ArchiveContentInclusionValidationResponse:
    """Validate report consistency without reading the submitted archives."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_ARCHIVE_CONTENT_INCLUSION_BODY_BYTES,
        too_large_error=ARCHIVE_CONTENT_INCLUSION_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        envelope = DiskSageArchiveContentInclusionEnvelope.model_validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=ARCHIVE_CONTENT_INCLUSION_INVALID_ERROR,
        ) from None
    return archive_content_inclusion_validation_response(envelope)
