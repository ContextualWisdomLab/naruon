"""Unit tests for the pure/validation logic in the judgment persistence service."""

from __future__ import annotations

import datetime

import pytest

from services.calendar_conflict_judgment_service import (
    _conflicts_to_json,
    apply_correction,
)
from services.calendar_conflict_policy import CalendarCommitment, CalendarConflictDecision


def _decision() -> CalendarConflictDecision:
    conflict = CalendarCommitment(
        commitment_id="existing-1",
        start_at=datetime.datetime(2026, 8, 17, 10, 30, tzinfo=datetime.timezone.utc),
        end_at=datetime.datetime(2026, 8, 17, 11, 30, tzinfo=datetime.timezone.utc),
        status="tentative",
    )
    return CalendarConflictDecision(
        decision_code="review_required",
        reason_code="lower_priority_conflict_requires_explicit_resolution",
        conflicts=(conflict,),
        recommended_action="Ask the proposer to confirm or reschedule.",
    )


def test_conflicts_to_json_serializes_iso_timestamps_and_status() -> None:
    """The persisted evidence blob must be plain JSON, not raw datetimes."""
    payload = _conflicts_to_json(_decision())

    assert payload == [
        {
            "commitment_id": "existing-1",
            "start_at": "2026-08-17T10:30:00+00:00",
            "end_at": "2026-08-17T11:30:00+00:00",
            "status": "tentative",
        }
    ]


@pytest.mark.asyncio
async def test_apply_correction_rejects_unsupported_status_code() -> None:
    """A bogus status_code must fail closed before any database lookup runs."""
    with pytest.raises(ValueError, match="status_code"):
        await apply_correction(
            object(),
            judgment_uid="conflict_judgment_test",
            user_id="user-1",
            organization_id=None,
            actor_user_id="user-1",
            correction_action="override",
            decision_code=None,
            status_code="not_a_real_status",
            rationale=None,
        )


@pytest.mark.asyncio
async def test_apply_correction_rejects_unsupported_decision_code() -> None:
    """A bogus decision_code must fail closed before any database lookup runs."""
    with pytest.raises(ValueError, match="decision_code"):
        await apply_correction(
            object(),
            judgment_uid="conflict_judgment_test",
            user_id="user-1",
            organization_id=None,
            actor_user_id="user-1",
            correction_action="override",
            decision_code="not_a_real_decision",
            status_code="confirmed",
            rationale=None,
        )
