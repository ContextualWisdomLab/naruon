"""Shared fail-closed parsing for small authenticated JSON evidence envelopes."""

from __future__ import annotations

import json

from fastapi import HTTPException, Request


MAX_JSON_NESTING_DEPTH = 128


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_non_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _validate_json_nesting_depth(value: str) -> None:
    """Reject excessive object/array nesting before the recursive JSON parser."""

    depth = 0
    in_string = False
    escaped = False
    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING_DEPTH:
                raise ValueError("JSON nesting depth exceeds limit")
        elif character in "]}":
            depth = max(0, depth - 1)


def validate_unique_json_object_keys(body: bytes) -> None:
    """Reject duplicate keys and non-finite constants before model validation."""

    text = body.decode("utf-8")
    _validate_json_nesting_depth(text)
    json.loads(
        text,
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
        if len(chunk) > max_body_bytes - len(body):
            raise HTTPException(status_code=413, detail=too_large_error)
        body.extend(chunk)
        if len(body) > max_body_bytes:
            raise HTTPException(status_code=413, detail=too_large_error)
    return bytes(body)
