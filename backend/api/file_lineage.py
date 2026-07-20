"""Authenticated, bounded structural validation for DiskSage file lineage."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.file_lineage import (
    DiskSageFileLineageEnvelope,
    FileLineageValidationResponse,
    validation_response,
)

router = APIRouter(prefix="/api/file-lineage", tags=["file-lineage"])

MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES = 256 * 1024
FILE_LINEAGE_TOO_LARGE_ERROR = "disksage_file_lineage_too_large"
FILE_LINEAGE_INVALID_ERROR = "disksage_file_lineage_invalid"


@router.post("/validate", response_model=FileLineageValidationResponse)
async def validate_disksage_file_lineage(
    request: Request,
) -> FileLineageValidationResponse:
    """Validate schema and claim consistency without verifying external evidence."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES,
        too_large_error=FILE_LINEAGE_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        envelope = DiskSageFileLineageEnvelope.model_validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=FILE_LINEAGE_INVALID_ERROR,
        ) from None
    return validation_response(envelope)
