"""Shared fail-closed parsing for small authenticated JSON evidence envelopes."""

from __future__ import annotations

import json

from fastapi import HTTPException, Request


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_non_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def validate_unique_json_object_keys(body: bytes) -> None:
    """Reject duplicate keys and non-finite constants before model validation."""

    json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_json_constant,
    )


async def read_bounded_body(
    request: Request,
    *,
    max_body_bytes: int,
    too_large_error: str,
) -> bytes:
    """Read at most ``max_body_bytes`` without trusting Content-Length."""

    raw_content_length = request.headers.get("content-length")
    if raw_content_length is not None:
        try:
            content_length = int(raw_content_length)
        except ValueError:
            content_length = max_body_bytes + 1
        if content_length < 0 or content_length > max_body_bytes:
            raise HTTPException(status_code=413, detail=too_large_error)

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_body_bytes:
            raise HTTPException(status_code=413, detail=too_large_error)
    return bytes(body)
