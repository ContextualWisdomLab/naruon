"""Authenticated, bounded structural validation for DiskSage file lineage."""

import json

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


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_non_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _parse_strict_json_body(body: bytes) -> object:
    return json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_json_constant,
    )


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
    """Validate schema and claim consistency without verifying external evidence."""

    body = await _read_bounded_body(request)
    try:
        parsed_body = _parse_strict_json_body(body)
        envelope = DiskSageFileLineageEnvelope.model_validate(parsed_body)
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
