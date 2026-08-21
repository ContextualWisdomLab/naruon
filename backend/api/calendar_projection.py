"""LineageWeave-facing, service-authenticated calendar read projection API."""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from api.calendar_projection_auth import (
    CalendarProjectionServiceContext,
    get_calendar_projection_service_context,
)
from services.calendar_projection import (
    MAXIMUM_CALENDAR_PROJECTION_EVENTS,
    MAXIMUM_CALENDAR_PROJECTION_WINDOW_DAYS,
    NARUON_CALENDAR_MEDIA_TYPE,
    CalendarProjectionContractError,
    CalendarProjectionPage,
    CalendarProjectionProvider,
    CalendarProjectionUnavailable,
    parse_calendar_projection_timestamp,
    unconfigured_calendar_projection_provider,
    validate_calendar_projection_cursor,
)

router = APIRouter(prefix="/api/calendar", tags=["calendar-projection"])


class CalendarProjectionJSONResponse(JSONResponse):
    """JSON response carrying the exact versioned calendar media type."""

    media_type = NARUON_CALENDAR_MEDIA_TYPE


async def get_calendar_projection_provider() -> CalendarProjectionProvider:
    """Return the fail-closed provider port until inbound sync is configured."""

    return unconfigured_calendar_projection_provider


def _query_error(error_code: str) -> HTTPException:
    """Return one stable non-disclosing invalid-query response."""

    return HTTPException(
        status_code=422,
        detail={"error_code": error_code},
    )


def _validated_window(
    window_start: str,
    window_end: str,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Parse and bound an exact calendar projection query window."""

    try:
        starts_at = parse_calendar_projection_timestamp(
            window_start,
            field_name="window_start",
        )
        ends_at = parse_calendar_projection_timestamp(
            window_end,
            field_name="window_end",
        )
    except CalendarProjectionContractError:
        raise _query_error("calendar_projection_timestamp_invalid") from None
    if ends_at <= starts_at:
        raise _query_error("calendar_projection_window_invalid")
    if ends_at - starts_at > datetime.timedelta(
        days=MAXIMUM_CALENDAR_PROJECTION_WINDOW_DAYS
    ):
        raise _query_error("calendar_projection_window_too_large")
    return starts_at, ends_at


def _validated_cursor(cursor: str | None) -> str | None:
    """Validate an optional opaque page cursor for a public API query."""

    if cursor is None:
        return None
    try:
        return validate_calendar_projection_cursor(cursor)
    except CalendarProjectionContractError:
        raise _query_error("calendar_projection_cursor_invalid") from None


@router.get(
    "/events",
    response_class=CalendarProjectionJSONResponse,
    response_model=None,
)
async def list_calendar_projection_events(
    window_start: Annotated[str, Query(min_length=1, max_length=64)],
    window_end: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[
        int,
        Query(ge=1, le=MAXIMUM_CALENDAR_PROJECTION_EVENTS),
    ] = MAXIMUM_CALENDAR_PROJECTION_EVENTS,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    service_context: CalendarProjectionServiceContext = Depends(
        get_calendar_projection_service_context
    ),
    provider: CalendarProjectionProvider = Depends(
        get_calendar_projection_provider
    ),
) -> CalendarProjectionJSONResponse:
    """Return one bounded, policy-filtered provider occurrence page.

    This endpoint authenticates an audience-scoped service rather than a browser
    user. The provider port is intentionally unavailable until Naruon has a real
    inbound CalDAV/event projection with revision and reconciliation evidence.
    """

    starts_at, ends_at = _validated_window(window_start, window_end)
    admitted_cursor = _validated_cursor(cursor)
    try:
        page = await provider.list_events(
            organization_id=service_context.organization_id,
            workspace_id=service_context.workspace_id,
            window_start=starts_at,
            window_end=ends_at,
            maximum_events=limit,
            cursor=admitted_cursor,
        )
    except CalendarProjectionUnavailable:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "calendar_projection_unavailable"},
            headers={"Retry-After": "60"},
        ) from None
    if not isinstance(page, CalendarProjectionPage):
        raise HTTPException(
            status_code=503,
            detail={"error_code": "calendar_projection_invalid"},
            headers={"Retry-After": "60"},
        )
    return CalendarProjectionJSONResponse(
        content=page.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )
