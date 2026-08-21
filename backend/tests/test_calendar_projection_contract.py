"""Strict model and schema tests for the Naruon calendar projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from services.calendar_projection import (
    MAXIMUM_CALENDAR_PROJECTION_EVENTS,
    NARUON_CALENDAR_SCHEMA_VERSION,
    CalendarProjectionContractError,
    CalendarProjectionOccurrence,
    CalendarProjectionPage,
    parse_calendar_projection_timestamp,
    unconfigured_calendar_projection_provider,
    validate_calendar_projection_cursor,
)


def _occurrence(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
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
    value.update(overrides)
    return value


def test_projection_models_preserve_exact_provider_evidence() -> None:
    occurrence = CalendarProjectionOccurrence.model_validate(_occurrence())
    page = CalendarProjectionPage(
        projection_revision="projection_001",
        events=(occurrence,),
        next_cursor="cursor_002",
    )

    assert page.schema_version == NARUON_CALENDAR_SCHEMA_VERSION
    assert page.events[0].provider_revision == 'W/"revision-7"'
    assert page.events[0].truth_status_code == "observed"
    assert page.model_dump(mode="json")["events"][0]["starts_at"] == (
        "2026-08-24T09:00:00+09:00"
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("event_reference", "https://provider.example/event/1"),
        ("occurrence_reference", "occurrence one"),
        ("source_reference", " source_001"),
        ("provider_revision", "https://provider.example/revision/1"),
        ("display_text", " Customer review"),
        ("time_zone", "Asia / Seoul"),
        ("starts_at", "2026-08-24T09:00:00"),
        ("ends_at", "2026-08-24T08:00:00+09:00"),
        ("observed_at", "not-a-time"),
        ("status_code", "unknown"),
        ("disclosure_code", "private_body"),
        ("truth_status_code", "authoritative"),
    ],
)
def test_projection_occurrence_rejects_contract_drift(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises((ValidationError, CalendarProjectionContractError)):
        CalendarProjectionOccurrence.model_validate(
            _occurrence(**{field_name: value})
        )


def test_projection_page_rejects_duplicate_occurrences() -> None:
    occurrence = CalendarProjectionOccurrence.model_validate(_occurrence())

    with pytest.raises((ValidationError, CalendarProjectionContractError)):
        CalendarProjectionPage(
            projection_revision="projection_001",
            events=(occurrence, occurrence),
        )


def test_projection_page_rejects_more_than_contract_limit() -> None:
    occurrences = tuple(
        CalendarProjectionOccurrence.model_validate(
            _occurrence(occurrence_reference=f"occurrence_{index}")
        )
        for index in range(MAXIMUM_CALENDAR_PROJECTION_EVENTS + 1)
    )

    with pytest.raises((ValidationError, CalendarProjectionContractError)):
        CalendarProjectionPage(
            projection_revision="projection_001",
            events=occurrences,
        )


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-21T09:00:00",
        "2026-08-21 09:00:00Z",
        "2026-13-21T09:00:00Z",
        " 2026-08-21T09:00:00Z",
    ],
)
def test_timestamp_parser_rejects_non_rfc3339_or_normalized_input(value: str) -> None:
    with pytest.raises(CalendarProjectionContractError):
        parse_calendar_projection_timestamp(value, field_name="observed_at")


@pytest.mark.parametrize(
    "value",
    [
        "https://provider.example/cursor",
        "cursor with spaces",
        " cursor_001",
        "cursor_001\nsecond",
    ],
)
def test_cursor_rejects_url_whitespace_and_control_values(value: str) -> None:
    with pytest.raises(CalendarProjectionContractError):
        validate_calendar_projection_cursor(value)


@pytest.mark.asyncio
async def test_unconfigured_provider_fails_closed() -> None:
    with pytest.raises(Exception) as captured:
        await unconfigured_calendar_projection_provider.list_events(
            organization_id="org-acme",
            workspace_id="workspace-org-acme",
            window_start=parse_calendar_projection_timestamp(
                "2026-08-01T00:00:00Z",
                field_name="window_start",
            ),
            window_end=parse_calendar_projection_timestamp(
                "2026-08-02T00:00:00Z",
                field_name="window_end",
            ),
            maximum_events=200,
            cursor=None,
        )

    assert type(captured.value).__name__ == "CalendarProjectionUnavailable"


def test_provider_schema_matches_runtime_contract() -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "contracts"
        / "naruon-calendar-projection-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    occurrence_schema = schema["$defs"]["calendar_occurrence"]

    assert schema["properties"]["schema_version"]["const"] == (
        NARUON_CALENDAR_SCHEMA_VERSION
    )
    assert schema["properties"]["events"]["maxItems"] == (
        MAXIMUM_CALENDAR_PROJECTION_EVENTS
    )
    assert set(occurrence_schema["required"]) == set(
        CalendarProjectionOccurrence.model_fields
    )
    assert occurrence_schema["properties"]["truth_status_code"]["const"] == (
        "observed"
    )
