"""API contracts for persisted calendar-conflict judgments and corrections."""

from __future__ import annotations

import datetime

import httpx
import pytest

import api.calendar_conflicts as calendar_conflicts_api
from api.calendar_conflicts import CalendarConflictJudgmentNotFoundError
from db.session import get_db
from main import app


def _client(*, user_id: str, organization_id: str | None = None) -> httpx.AsyncClient:
    headers = {"X-User-Id": user_id}
    if organization_id is not None:
        headers["X-Organization-Id"] = organization_id
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers=headers,
    )


class _FakeJudgment:
    def __init__(self, **overrides: object) -> None:
        observed_at = datetime.datetime(2026, 8, 30, 0, 0, tzinfo=datetime.timezone.utc)
        defaults = {
            "judgment_uid": "conflict_judgment_test",
            "proposed_commitment_id": "proposal-1",
            "source_thread_id": "thread-1",
            "source_message_id": "<msg-1@example.com>",
            "decision_code": "review_required",
            "reason_code": "lower_priority_conflict_requires_explicit_resolution",
            "conflicts_json": [
                {
                    "commitment_id": "existing-1",
                    "start_at": "2026-08-17T10:30:00+00:00",
                    "end_at": "2026-08-17T11:30:00+00:00",
                    "status": "tentative",
                }
            ],
            "recommended_action": "Ask the proposer to confirm or reschedule.",
            "policy_version": "status-weighted-v1",
            "status_code": "proposed",
            "created_at": observed_at,
            "updated_at": observed_at,
        }
        defaults.update(overrides)
        self.__dict__.update(defaults)


class _FakeCorrection:
    def __init__(self, **overrides: object) -> None:
        observed_at = datetime.datetime(2026, 8, 30, 0, 0, tzinfo=datetime.timezone.utc)
        defaults = {
            "correction_uid": "conflict_correction_test",
            "correction_action": "override_decision",
            "before_json": {"decision_code": "review_required", "status_code": "proposed"},
            "after_json": {"decision_code": "available", "status_code": "overridden"},
            "rationale": "Confirmed with the proposer directly.",
            "actor_user_id": "reviewer",
            "created_at": observed_at,
        }
        defaults.update(overrides)
        self.__dict__.update(defaults)


def _proposed_vs_tentative_payload() -> dict[str, object]:
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
        "source_thread_id": "thread-1",
        "source_message_id": "<msg-1@example.com>",
    }


class _DummySession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_create_judgment_persists_decision_and_returns_it(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """Creating a judgment evaluates the policy once and hands back the persisted row."""
    captured = {}
    dummy_session = _DummySession()

    async def fake_create_judgment(session, **kwargs):
        captured["session"] = session
        captured.update(kwargs)
        return _FakeJudgment()

    async def override_get_db():
        yield dummy_session

    monkeypatch.setattr(calendar_conflicts_api, "create_judgment", fake_create_judgment)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer", organization_id="org-acme") as client:
            response = await client.post(
                "/api/calendar/conflicts/judgments",
                json=_proposed_vs_tentative_payload(),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert dummy_session.committed is True
    assert captured["session"] is dummy_session
    assert captured["user_id"] == "reviewer"
    assert captured["organization_id"] == "org-acme"
    assert captured["proposed_commitment_id"] == "proposal-1"
    assert captured["source_thread_id"] == "thread-1"
    assert captured["source_message_id"] == "<msg-1@example.com>"
    assert captured["decision"].decision_code == "review_required"

    body = response.json()
    assert body["judgment_uid"] == "conflict_judgment_test"
    assert body["status_code"] == "proposed"
    assert body["conflicts"][0]["commitment_id"] == "existing-1"


@pytest.mark.asyncio
async def test_create_judgment_rejects_malformed_request_without_persisting(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """A policy-invalid request must never reach the persistence call."""
    calls = []

    async def fake_create_judgment(session, **kwargs):
        calls.append(kwargs)
        return _FakeJudgment()

    async def override_get_db():
        yield _DummySession()

    monkeypatch.setattr(calendar_conflicts_api, "create_judgment", fake_create_judgment)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer") as client:
            response = await client.post(
                "/api/calendar/conflicts/judgments",
                json={"existing": []},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert response.json()["error_code"] == "calendar_proposed_source_missing"
    assert calls == []


@pytest.mark.asyncio
async def test_list_judgments_scopes_by_source_thread_id(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """Listing must forward the caller's own scope and the thread filter untouched."""
    captured = {}

    async def fake_list_judgments(session, **kwargs):
        captured.update(kwargs)
        return [_FakeJudgment()]

    async def override_get_db():
        yield _DummySession()

    monkeypatch.setattr(calendar_conflicts_api, "list_judgments", fake_list_judgments)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer", organization_id="org-acme") as client:
            response = await client.get(
                "/api/calendar/conflicts/judgments",
                params={"source_thread_id": "thread-1"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert captured["user_id"] == "reviewer"
    assert captured["organization_id"] == "org-acme"
    assert captured["source_thread_id"] == "thread-1"
    assert response.json()[0]["judgment_uid"] == "conflict_judgment_test"


@pytest.mark.asyncio
async def test_correct_judgment_returns_audit_trail_and_commits(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """A correction call commits and returns the full before/after audit trail."""
    captured = {}
    dummy_session = _DummySession()

    async def fake_apply_correction(session, **kwargs):
        captured["session"] = session
        captured.update(kwargs)
        return _FakeCorrection()

    async def override_get_db():
        yield dummy_session

    monkeypatch.setattr(calendar_conflicts_api, "apply_correction", fake_apply_correction)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer", organization_id="org-acme") as client:
            response = await client.post(
                "/api/calendar/conflicts/judgments/conflict_judgment_test/corrections",
                json={
                    "correction_action": "override_decision",
                    "decision_code": "available",
                    "status_code": "overridden",
                    "rationale": "Confirmed with the proposer directly.",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert dummy_session.committed is True
    assert captured["judgment_uid"] == "conflict_judgment_test"
    assert captured["actor_user_id"] == "reviewer"
    assert captured["decision_code"] == "available"
    assert captured["status_code"] == "overridden"

    body = response.json()
    assert body["correction_uid"] == "conflict_correction_test"
    assert body["after_json"]["status_code"] == "overridden"


@pytest.mark.asyncio
async def test_correct_judgment_404s_when_outside_caller_scope(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """A judgment_uid outside the caller's own scope must never leak as a 500 or a silent no-op."""

    async def fake_apply_correction(session, **kwargs):
        raise CalendarConflictJudgmentNotFoundError(
            "Calendar conflict judgment is outside the requested scope"
        )

    async def override_get_db():
        yield _DummySession()

    monkeypatch.setattr(calendar_conflicts_api, "apply_correction", fake_apply_correction)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer") as client:
            response = await client.post(
                "/api/calendar/conflicts/judgments/not-mine/corrections",
                json={"correction_action": "override_decision", "status_code": "overridden"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
