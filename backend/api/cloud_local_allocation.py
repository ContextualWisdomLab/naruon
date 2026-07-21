"""Authenticated bounded validation for DiskSage cloud allocation evidence."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.cloud_local_allocation import (
    CloudLocalAllocationValidationResponse,
    DiskSageCloudLocalAllocationInventory,
    validation_response,
)


router = APIRouter(
    prefix="/api/cloud-local-allocation",
    tags=["cloud-local-allocation"],
)

MAX_DISKSAGE_CLOUD_LOCAL_ALLOCATION_BODY_BYTES = 16 * 1024 * 1024
CLOUD_LOCAL_ALLOCATION_TOO_LARGE_ERROR = "disksage_cloud_local_allocation_too_large"
CLOUD_LOCAL_ALLOCATION_INVALID_ERROR = "disksage_cloud_local_allocation_invalid"


@router.post("/validate", response_model=CloudLocalAllocationValidationResponse)
async def validate_disksage_cloud_local_allocation(
    request: Request,
) -> CloudLocalAllocationValidationResponse:
    """Validate a report without reading, opening, or mutating any submitted path."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_CLOUD_LOCAL_ALLOCATION_BODY_BYTES,
        too_large_error=CLOUD_LOCAL_ALLOCATION_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        inventory = DiskSageCloudLocalAllocationInventory.model_validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=CLOUD_LOCAL_ALLOCATION_INVALID_ERROR,
        ) from None
    return validation_response(inventory)
