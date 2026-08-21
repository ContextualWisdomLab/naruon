"""Provider-side contract tests for LineageWeave calendar observations."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from api import calendar_projection as calendar_projection_api
from api.calendar_projection_auth import CalendarProjectionServiceContext
from main import app
from services.calendar_projection import (
    CalendarProjectionOccurrence,
    CalendarProjectionPage,
    CalendarProjectionUnavailable,
)


@dataclass
class RecordingProjectionProvider:
    """Fixture provider that records the authorization and bounded query."""

    page: CalendarProjectionPage
    calls: list[dict[str, object]]

    async def list_events(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
        maximum_events: int,
        cursor: str | None,
    ) -> CalendarProjectionPage:
        self.calls.append(
            {
                "organization_id": organization_id,
                "workspace_id": workspace_id,
                "window_start": window_start,
                "window_end": window_end,
                "maximum_events": maximum_events,
                "cursor": cursor,
            }
        )
        return self.page


class UnavailableProjectionProvider:
    """Fixture provider that proves unavailable state is explicit."""

    async def list_events(self, **_kwargs) -> CalendarProjectionPage:
        raise CalendarProjectionUnavailable


def _service_context() -> CalendarProjectionServiceContext:
    return CalendarProjectionServiceContext(
        service_subject="service-lineageweave",
        organization_id="org-acme",
        workspace_id="workspace-org-acme",
        audience="naruon-calendar-read",
        scopes=frozenset({"calendar:read"}),
    )


def _page() -> CalendarProjectionPage:
    return CalendarProjectionPage(
        schema_version="1.0",
        projection_revision="projection_001",
        events=(
            CalendarProjectionOccurrence(
                event_reference="event_001",
                occurrence_reference="occurrence_001",
                source_reference="source_001",
                provider_revision='W/"revision-7"',
                display_text="Customer review",
                starts_at="2026-08-24T09:00:00+09:00",
                ends_at="2026-08-24T10:00:00+09:00",
                all_day=False,
                time_zone="Asia/Seoul",
                status_code="confirmed",
                disclosure_code="summary_visible",
                truth_status_code="observed",
                observed_at="2026-08-21T00:00:00Z",
            ),
        ),
        next_cursor="cursor_002",
    )


@pytest.fixture
def projection_overrides():
    def apply(provider) -> None:
        async def service_context_override() -> CalendarProjectionServiceContext:
            return _service_context()

        async def provider_override():
            return provider

        app.dependency_overrides[
            calendar_projection_api.get_calendar_projection_service_context
        ] = service_context_override
        app.dependency_overrides[
            calendar_projection_api.get_calendar_projection_provider
        ] = provider_override

    yield apply
    app.dependency_overrides.pop(
        calendar_projection_api.get_calendar_projection_service_context,
        None,
    )
    app.dependency_overrides.pop(
        calendar_projection_api.get_calendar_projection_provider,
        None,
    )


def test_calendar_projection_route_is_not_guarded_by_end_user_auth(
    projection_overrides,
) -> None:
    provider = RecordingProjectionProvider(_page(), [])
    projection_overrides(provider)
    client = TestClient(app)

    response = client.get(
        "/api/calendar/events",
        params={
            "window_start": "2026-08-01T00:00:00Z",
            "window_end": "2026-09-01T00:00:00Z",
            "limit": "25",
            "cursor": "cursor_001",
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == (
        "application/vnd.contextualwisdomlab.naruon-calendar.v1+json"
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "schema_version": "1.0",
        "projection_revision": "projection_001",
        "events": [
            {
                "event_reference": "event_001",
                "occurrence_reference": "occurrence_001",
                "source_reference": "source_001",
                "provider_revision": 'W/"revision-7"',
                "display_text": "Customer review",
                "starts_at": "2026-08-24T09:00:00+09:00",
                "ends_at": "2026-08-24T10:00:00+09:00",
                "all_day": False,
                "time_zone": "Asia/Seoul",
                "status_code": "confirmed",
                "disclosure_code": "summary_visible",
                "truth_status_code": "observed",
                "observed_at": "2026-08-21T00:00:00Z",
            }
        ],
        "next_cursor": "cursor_002",
    }
    assert provider.calls == [
        {
            "organization_id": "org-acme",
            "workspace_id": "workspace-org-acme",
            "window_start": datetime.datetime(
                2026,
                8,
                1,
                tzinfo=datetime.timezone.utc,
            ),
            "window_end": datetime.datetime(
                2026,
                9,
                1,
                tzinfo=datetime.timezone.utc,
            ),
            "maximum_events": 25,
            "cursor": "cursor_001",
        }
    ]


@pytest.mark.parametrize(
    ("params", "error_code"),
    [
        (
            {
                "window_start": "2026-08-01T00:00:00",
                "window_end": "2026-08-02T00:00:00Z",
            },
            "calendar_projection_timestamp_invalid",
        ),
        (
            {
                "window_start": "2026-08-02T00:00:00Z",
                "window_end": "2026-08-01T00:00:00Z",
            },
            "calendar_projection_window_invalid",
        ),
        (
            {
                "window_start": "2026-01-01T00:00:00Z",
                "window_end": "2027-01-03T00:00:00Z",
            },
            "calendar_projection_window_too_large",
        ),
        (
            {
                "window_start": "2026-08-01T00:00:00Z",
                "window_end": "2026-08-02T00:00:00Z",
                "cursor": "https://provider.example/private",
            },
            "calendar_projection_cursor_invalid",
        ),
    ],
)
def test_calendar_projection_rejects_invalid_queries_before_provider(
    projection_overrides,
    params: dict[str, str],
    error_code: str,
) -> None:
    provider = RecordingProjectionProvider(_page(), [])
    projection_overrides(provider)
    client = TestClient(app)

    response = client.get("/api/calendar/events", params=params)

    assert response.status_code == 422
    assert response.json() == {"detail": {"error_code": error_code}}
    assert provider.calls == []


def test_calendar_projection_rejects_page_limit_over_contract(
    projection_overrides,
) -> None:
    provider = RecordingProjectionProvider(_page(), [])
    projection_overrides(provider)
    client = TestClient(app)

    response = client.get(
        "/api/calendar/events",
        params={
            "window_start": "2026-08-01T00:00:00Z",
            "window_end": "2026-08-02T00:00:00Z",
            "limit": "201",
        },
    )

    assert response.status_code == 422
    assert provider.calls == []


def test_calendar_projection_returns_explicit_unavailable_state(
    projection_overrides,
) -> None:
    projection_overrides(UnavailableProjectionProvider())
    client = TestClient(app)

    response = client.get(
        "/api/calendar/events",
        params={
            "window_start": "2026-08-01T00:00:00Z",
            "window_end": "2026-08-02T00:00:00Z",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"error_code": "calendar_projection_unavailable"}
    }
    assert response.headers["retry-after"] == "60"


def test_main_registers_service_projection_router_without_private_dependency() -> None:
    matching_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/calendar/events"
    ]

    assert len(matching_routes) == 1
    route = matching_routes[0]
    dependency_names = {
        dependency.call.__name__
        for dependency in route.dependant.dependencies
        if dependency.call is not None
    }
    assert "get_calendar_projection_service_context" in dependency_names
    assert "get_auth_context" not in dependency_names
