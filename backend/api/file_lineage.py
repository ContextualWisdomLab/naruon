"""Authenticated, bounded structural validation for DiskSage file lineage."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from services.file_lineage import (
    DiskSageFileLineageEnvelope,
    FileLineageValidationResponse,
    validation_response,
)

router = APIRouter(prefix="/api/file-lineage", tags=["file-lineage"])

MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES = 256 * 1024
FILE_LINEAGE_TOO_LARGE_ERROR = "disksage_file_lineage_too_large"
FILE_LINEAGE_INVALID_ERROR = "disksage_file_lineage_invalid"


async def _read_bounded_body(request: Request) -> bytes:
    raw_content_length = request.headers.get("content-length")
    if raw_content_length is not None:
        try:
            content_length = int(raw_content_length)
        except ValueError:
            content_length = MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES + 1
        if content_length < 0 or content_length > MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES:
            raise HTTPException(status_code=413, detail=FILE_LINEAGE_TOO_LARGE_ERROR)

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES:
            raise HTTPException(status_code=413, detail=FILE_LINEAGE_TOO_LARGE_ERROR)
    return bytes(body)


@router.post("/validate", response_model=FileLineageValidationResponse)
async def validate_disksage_file_lineage(
    request: Request,
) -> FileLineageValidationResponse:
    """Validate shape and policy invariants without claiming provenance integrity."""

    body = await _read_bounded_body(request)
    try:
        envelope = DiskSageFileLineageEnvelope.model_validate_json(body)
    except (ValidationError, ValueError):
        raise HTTPException(
            status_code=422,
            detail=FILE_LINEAGE_INVALID_ERROR,
        ) from None
    return validation_response(envelope)
