"""Authenticated, bounded validation for redacted DiskSage capacity evidence."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.cloud_capacity_assessment import (
    CloudCapacityValidationResponse,
    DiskSageCloudCapacityEnvelope,
    cloud_capacity_validation_response,
)


router = APIRouter(
    prefix="/api/cloud-capacity-assessment",
    tags=["cloud-capacity-assessment"],
)

MAX_DISKSAGE_CLOUD_CAPACITY_BODY_BYTES = 64 * 1024
CLOUD_CAPACITY_TOO_LARGE_ERROR = "disksage_cloud_capacity_assessment_too_large"
CLOUD_CAPACITY_INVALID_ERROR = "disksage_cloud_capacity_assessment_invalid"


@router.post("/validate", response_model=CloudCapacityValidationResponse)
async def validate_disksage_cloud_capacity(
    request: Request,
) -> CloudCapacityValidationResponse:
    """Validate redacted claim consistency without contacting a provider."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_CLOUD_CAPACITY_BODY_BYTES,
        too_large_error=CLOUD_CAPACITY_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        envelope = DiskSageCloudCapacityEnvelope.model_validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=CLOUD_CAPACITY_INVALID_ERROR,
        ) from None
    return cloud_capacity_validation_response(envelope)
