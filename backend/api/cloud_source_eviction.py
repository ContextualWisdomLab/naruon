"""Authenticated bounded validation for DiskSage cloud source eviction evidence."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import TypeAdapter, ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.cloud_source_eviction import (
    CloudSourceEvictionValidationResponse,
    DiskSageCloudSourceEvictionOutput,
    validation_response,
)


router = APIRouter(
    prefix="/api/cloud-source-eviction",
    tags=["cloud-source-eviction"],
)

MAX_DISKSAGE_CLOUD_SOURCE_EVICTION_BODY_BYTES = 1024 * 1024
CLOUD_SOURCE_EVICTION_TOO_LARGE_ERROR = "disksage_cloud_source_eviction_too_large"
CLOUD_SOURCE_EVICTION_INVALID_ERROR = "disksage_cloud_source_eviction_invalid"
EVIDENCE_ADAPTER = TypeAdapter(DiskSageCloudSourceEvictionOutput)


@router.post("/validate", response_model=CloudSourceEvictionValidationResponse)
async def validate_disksage_cloud_source_eviction(
    request: Request,
) -> CloudSourceEvictionValidationResponse:
    """Validate claims without opening, mutating, or persisting a submitted path."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_CLOUD_SOURCE_EVICTION_BODY_BYTES,
        too_large_error=CLOUD_SOURCE_EVICTION_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        evidence = EVIDENCE_ADAPTER.validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=CLOUD_SOURCE_EVICTION_INVALID_ERROR,
        ) from None
    return validation_response(evidence)
