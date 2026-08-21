"""Naruon-owned provider contract for bounded calendar read projections."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

NARUON_CALENDAR_SCHEMA_VERSION = "1.0"
NARUON_CALENDAR_MEDIA_TYPE = (
    "application/vnd.contextualwisdomlab.naruon-calendar.v1+json"
)
MAXIMUM_CALENDAR_PROJECTION_EVENTS = 200
MAXIMUM_CALENDAR_PROJECTION_WINDOW_DAYS = 366
MAXIMUM_CALENDAR_PROJECTION_CURSOR_LENGTH = 1024
_RFC3339_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:"
    r"[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$"
)


class CalendarProjectionContractError(ValueError):
    """A provider projection value violated the public calendar contract."""


class CalendarProjectionUnavailable(RuntimeError):
    """No authoritative provider projection is currently configured."""


def _exact_text(
    value: Any,
    *,
    field_name: str,
    maximum_length: int,
    allow_internal_whitespace: bool = True,
    allow_url_shape: bool = True,
) -> str:
    """Validate exact bounded text without silently normalizing identity."""

    if not isinstance(value, str):
        raise CalendarProjectionContractError(f"{field_name} must be a string")
    if value != value.strip():
        raise CalendarProjectionContractError(
            f"{field_name} must not contain surrounding whitespace"
        )
    if not value or len(value) > maximum_length:
        raise CalendarProjectionContractError(
            f"{field_name} must contain 1..{maximum_length} characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CalendarProjectionContractError(
            f"{field_name} contains control characters"
        )
    if not allow_internal_whitespace and any(
        character.isspace() for character in value
    ):
        raise CalendarProjectionContractError(
            f"{field_name} must be an opaque token without whitespace"
        )
    if not allow_url_shape and "://" in value:
        raise CalendarProjectionContractError(
            f"{field_name} must not contain a URL"
        )
    return value


def parse_calendar_projection_timestamp(
    value: Any,
    *,
    field_name: str,
) -> datetime:
    """Return one exact offset-aware RFC 3339 timestamp."""

    text = _exact_text(
        value,
        field_name=field_name,
        maximum_length=64,
        allow_internal_whitespace=False,
    )
    if _RFC3339_PATTERN.fullmatch(text) is None:
        raise CalendarProjectionContractError(
            f"{field_name} must be RFC 3339"
        )
    normalized = text[:10] + "T" + text[11:]
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CalendarProjectionContractError(
            f"{field_name} must be RFC 3339"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CalendarProjectionContractError(
            f"{field_name} must include an offset"
        )
    return parsed


def validate_calendar_projection_cursor(value: Any) -> str:
    """Validate one opaque bounded page cursor."""

    return _exact_text(
        value,
        field_name="cursor",
        maximum_length=MAXIMUM_CALENDAR_PROJECTION_CURSOR_LENGTH,
        allow_internal_whitespace=False,
        allow_url_shape=False,
    )


def _opaque_reference(value: Any, field_name: str) -> str:
    """Validate a bounded opaque non-URL reference."""

    return _exact_text(
        value,
        field_name=field_name,
        maximum_length=256,
        allow_internal_whitespace=False,
        allow_url_shape=False,
    )


class CalendarProjectionOccurrence(BaseModel):
    """One policy-filtered provider occurrence observed by Naruon."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_reference: str
    occurrence_reference: str
    source_reference: str
    provider_revision: str
    display_text: str
    starts_at: str
    ends_at: str
    all_day: bool
    time_zone: str
    status_code: Literal["confirmed", "tentative", "desired", "cancelled"]
    disclosure_code: Literal["busy_only", "summary_visible"]
    truth_status_code: Literal["observed"] = "observed"
    observed_at: str

    @field_validator(
        "event_reference",
        "occurrence_reference",
        "source_reference",
        mode="before",
    )
    @classmethod
    def validate_opaque_references(cls, value: Any, info) -> str:
        """Reject URL-shaped, whitespace-bearing, or unbounded references."""

        return _opaque_reference(value, str(info.field_name))

    @field_validator("provider_revision", mode="before")
    @classmethod
    def validate_provider_revision(cls, value: Any) -> str:
        """Keep one bounded provider revision without provider URLs."""

        return _exact_text(
            value,
            field_name="provider_revision",
            maximum_length=256,
            allow_url_shape=False,
        )

    @field_validator("display_text", mode="before")
    @classmethod
    def validate_display_text(cls, value: Any) -> str:
        """Keep only bounded policy-filtered buyer display text."""

        return _exact_text(
            value,
            field_name="display_text",
            maximum_length=512,
        )

    @field_validator("time_zone", mode="before")
    @classmethod
    def validate_time_zone(cls, value: Any) -> str:
        """Validate one bounded IANA-style timezone token."""

        return _exact_text(
            value,
            field_name="time_zone",
            maximum_length=128,
            allow_internal_whitespace=False,
        )

    @field_validator("starts_at", "ends_at", "observed_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any, info) -> str:
        """Validate one exact offset-aware occurrence timestamp."""

        parse_calendar_projection_timestamp(
            value,
            field_name=str(info.field_name),
        )
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "CalendarProjectionOccurrence":
        """Require every occurrence to end strictly after it starts."""

        starts_at = parse_calendar_projection_timestamp(
            self.starts_at,
            field_name="starts_at",
        )
        ends_at = parse_calendar_projection_timestamp(
            self.ends_at,
            field_name="ends_at",
        )
        if ends_at <= starts_at:
            raise CalendarProjectionContractError(
                "ends_at must be after starts_at"
            )
        return self


class CalendarProjectionPage(BaseModel):
    """One bounded page returned to a separately authenticated consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = NARUON_CALENDAR_SCHEMA_VERSION
    projection_revision: str
    events: tuple[CalendarProjectionOccurrence, ...]
    next_cursor: str | None = None

    @field_validator("projection_revision", mode="before")
    @classmethod
    def validate_projection_revision(cls, value: Any) -> str:
        """Validate one opaque provider projection revision."""

        return _opaque_reference(value, "projection_revision")

    @field_validator("next_cursor", mode="before")
    @classmethod
    def validate_next_cursor(cls, value: Any) -> str | None:
        """Validate an optional opaque cursor without accepting URLs."""

        if value is None:
            return None
        return validate_calendar_projection_cursor(value)

    @field_validator("events")
    @classmethod
    def validate_event_page_size(
        cls,
        value: tuple[CalendarProjectionOccurrence, ...],
    ) -> tuple[CalendarProjectionOccurrence, ...]:
        """Enforce the response page ceiling and occurrence uniqueness."""

        if len(value) > MAXIMUM_CALENDAR_PROJECTION_EVENTS:
            raise CalendarProjectionContractError(
                "events exceeds the admitted page size"
            )
        occurrence_references = [
            occurrence.occurrence_reference for occurrence in value
        ]
        if len(occurrence_references) != len(set(occurrence_references)):
            raise CalendarProjectionContractError(
                "events contains duplicate occurrence references"
            )
        return value


class CalendarProjectionProvider(Protocol):
    """Port implemented only by an authorized Naruon event projection."""

    async def list_events(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        window_start: datetime,
        window_end: datetime,
        maximum_events: int,
        cursor: str | None,
    ) -> CalendarProjectionPage:
        """Return one policy-filtered page or raise unavailable."""


class UnconfiguredCalendarProjectionProvider:
    """Production default that refuses to invent provider observations."""

    async def list_events(
        self,
        *,
        organization_id: str,
        workspace_id: str,
        window_start: datetime,
        window_end: datetime,
        maximum_events: int,
        cursor: str | None,
    ) -> CalendarProjectionPage:
        """Fail closed until inbound provider projection is configured."""

        del (
            organization_id,
            workspace_id,
            window_start,
            window_end,
            maximum_events,
            cursor,
        )
        raise CalendarProjectionUnavailable


unconfigured_calendar_projection_provider = (
    UnconfiguredCalendarProjectionProvider()
)
