"""Authenticated, bounded validation for DiskSage catalog candidate batches."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.file_catalog_candidate_batch import (
    DiskSageCatalogCandidateBatch,
    FileCatalogCandidateBatchValidationResponse,
    validation_response,
)


router = APIRouter(
    prefix="/api/file-catalog-candidate-batch",
    tags=["file-catalog-candidate-batch"],
)

MAX_DISKSAGE_FILE_CATALOG_BODY_BYTES = 2 * 1024 * 1024
FILE_CATALOG_TOO_LARGE_ERROR = "disksage_file_catalog_candidate_batch_too_large"
FILE_CATALOG_INVALID_ERROR = "disksage_file_catalog_candidate_batch_invalid"


@router.post(
    "/validate",
    response_model=FileCatalogCandidateBatchValidationResponse,
)
async def validate_disksage_file_catalog_candidate_batch(
    request: Request,
) -> FileCatalogCandidateBatchValidationResponse:
    """Validate the private metadata contract without persistence or side effects."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_FILE_CATALOG_BODY_BYTES,
        too_large_error=FILE_CATALOG_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        batch = DiskSageCatalogCandidateBatch.model_validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=FILE_CATALOG_INVALID_ERROR,
        ) from None
    return validation_response(batch)
