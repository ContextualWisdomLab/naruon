"""API contracts for buyer-visible calendar conflict decisions."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")

client = TestClient(app, headers={"X-User-Id": "calendar-conflict-user"})


def _request_payload() -> dict[str, object]:
    """Return one realistic confirmed-vs-tentative scheduling collision."""
    return {
        "proposed": {
            "commitment_id": "proposal-1",
            "start_at": "2026-08-17T10:00:00+09:00",
            "end_at": "2026-08-17T11:00:00+09:00",
            "status": "confirmed",
        },
        "existing": [
            {
                "commitment_id": "existing-1",
                "start_at": "2026-08-17T10:30:00+09:00",
                "end_at": "2026-08-17T11:30:00+09:00",
                "status": "tentative",
            }
        ],
    }


def test_calendar_conflict_decision_requires_explicit_review_for_lower_priority_overlap() -> None:
    """Customers must receive a concrete next action instead of silent displacement."""
    response = client.post(
        "/api/calendar/conflicts/evaluate",
        json=_request_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision_code": "review_required",
        "reason_code": "lower_priority_conflict_requires_explicit_resolution",
        "conflicts": [
            {
                "commitment_id": "existing-1",
                "start_at": "2026-08-17T10:30:00+09:00",
                "end_at": "2026-08-17T11:30:00+09:00",
                "status": "tentative",
            }
        ],
        "recommended_action": (
            "Review and explicitly reschedule or accept the lower-priority conflict "
            "before proceeding."
        ),
        "policy_version": "status-weighted-v1",
    }


def test_calendar_conflict_decision_rejects_naive_timestamps() -> None:
    """The public API must reject calendar instants without an explicit offset."""
    payload = _request_payload()
    proposed = payload["proposed"]
    assert isinstance(proposed, dict)
    proposed["start_at"] = "2026-08-17T10:00:00"

    response = client.post("/api/calendar/conflicts/evaluate", json=payload)

    assert response.status_code == 422


def test_calendar_conflict_decision_rejects_invalid_interval() -> None:
    """Zero-length or reversed intervals must fail closed before a decision is emitted."""
    payload = _request_payload()
    proposed = payload["proposed"]
    assert isinstance(proposed, dict)
    proposed["end_at"] = proposed["start_at"]

    response = client.post("/api/calendar/conflicts/evaluate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "end_at must be later than start_at"}


def test_calendar_conflict_decision_bounds_existing_evidence_batch() -> None:
    """A caller cannot send an unbounded provider calendar snapshot to the endpoint."""
    payload = _request_payload()
    existing = payload["existing"]
    assert isinstance(existing, list)
    payload["existing"] = existing * 501

    response = client.post("/api/calendar/conflicts/evaluate", json=payload)

    assert response.status_code == 422
