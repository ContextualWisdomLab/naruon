"""Authenticated bounded validation for DiskSage iCloud local eviction evidence."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import TypeAdapter, ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.cloud_local_eviction import (
    CloudLocalEvictionEvidence,
    CloudLocalEvictionValidationResponse,
    validation_response,
)


router = APIRouter(
    prefix="/api/cloud-local-eviction",
    tags=["cloud-local-eviction"],
)

MAX_DISKSAGE_CLOUD_LOCAL_EVICTION_BODY_BYTES = 1024 * 1024
CLOUD_LOCAL_EVICTION_TOO_LARGE_ERROR = "disksage_cloud_local_eviction_too_large"
CLOUD_LOCAL_EVICTION_INVALID_ERROR = "disksage_cloud_local_eviction_invalid"
EVIDENCE_ADAPTER = TypeAdapter(CloudLocalEvictionEvidence)


@router.post("/validate", response_model=CloudLocalEvictionValidationResponse)
async def validate_disksage_cloud_local_eviction(
    request: Request,
) -> CloudLocalEvictionValidationResponse:
    """Validate evidence without opening, mutating, or persisting a submitted path."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_CLOUD_LOCAL_EVICTION_BODY_BYTES,
        too_large_error=CLOUD_LOCAL_EVICTION_TOO_LARGE_ERROR,
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
            detail=CLOUD_LOCAL_EVICTION_INVALID_ERROR,
        ) from None
    return validation_response(evidence)
