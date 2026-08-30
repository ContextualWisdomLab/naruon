"""API contracts for persisted calendar-conflict judgments and corrections."""

from __future__ import annotations

import datetime
import json

import httpx
import pytest
from fastapi.exceptions import RequestValidationError

import api.calendar_conflicts as calendar_conflicts_api
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
    assert captured["workspace_id"] == "workspace-org-acme"
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
    assert captured["workspace_id"] == "workspace-org-acme"
    assert captured["source_thread_id"] == "thread-1"
    assert response.json()[0]["judgment_uid"] == "conflict_judgment_test"


@pytest.mark.asyncio
async def test_get_judgment_returns_it_by_uid(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """A single judgment must be fetchable by uid regardless of list ordering."""
    captured = {}

    async def fake_get_judgment(session, **kwargs):
        captured.update(kwargs)
        return _FakeJudgment()

    async def override_get_db():
        yield _DummySession()

    monkeypatch.setattr(calendar_conflicts_api, "get_judgment", fake_get_judgment)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer", organization_id="org-acme") as client:
            response = await client.get(
                "/api/calendar/conflicts/judgments/conflict_judgment_test"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert captured["judgment_uid"] == "conflict_judgment_test"
    assert captured["user_id"] == "reviewer"
    assert captured["organization_id"] == "org-acme"
    assert captured["workspace_id"] == "workspace-org-acme"
    assert response.json()["judgment_uid"] == "conflict_judgment_test"


@pytest.mark.asyncio
async def test_get_judgment_404s_when_outside_caller_scope(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """A judgment_uid outside the caller's own scope must 404, not leak another scope's data."""

    async def fake_get_judgment(session, **kwargs):
        raise calendar_conflicts_api.CalendarConflictJudgmentNotFoundError(
            "Calendar conflict judgment is outside the requested scope"
        )

    async def override_get_db():
        yield _DummySession()

    monkeypatch.setattr(calendar_conflicts_api, "get_judgment", fake_get_judgment)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer") as client:
            response = await client.get("/api/calendar/conflicts/judgments/not-mine")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


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
    assert captured["organization_id"] == "org-acme"
    assert captured["workspace_id"] == "workspace-org-acme"
    assert captured["decision_code"] == "available"
    assert captured["status_code"] == "overridden"

    body = response.json()
    assert body["correction_uid"] == "conflict_correction_test"
    assert body["after_json"]["status_code"] == "overridden"


@pytest.mark.asyncio
async def test_correct_judgment_rejects_incoherent_status_and_decision(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """Confirming a judgment while also changing its decision must fail closed at the request layer."""
    calls = []

    async def fake_apply_correction(session, **kwargs):
        calls.append(kwargs)
        return _FakeCorrection()

    async def override_get_db():
        yield _DummySession()

    monkeypatch.setattr(calendar_conflicts_api, "apply_correction", fake_apply_correction)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client(user_id="reviewer") as client:
            response = await client.post(
                "/api/calendar/conflicts/judgments/conflict_judgment_test/corrections",
                json={
                    "correction_action": "confirm_decision",
                    "decision_code": "available",
                    "status_code": "confirmed",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert response.json()["error_code"] == "calendar_correction_incoherent"
    assert calls == []


def test_request_validation_error_response_dispatches_by_type_not_wording():
    """The error_code mapper must key off errors()[i]["type"], never ["msg"].

    Constructs a RequestValidationError whose message text does not contain
    any of the phrases the mapper used to substring-match on -- proving the
    dispatch is now driven entirely by the stable ``type`` a
    PydanticCustomError carries, independent of how either error is worded.
    """
    exc = RequestValidationError(
        [
            {
                "type": "calendar_correction_incoherent",
                "msg": "this message says nothing about decision codes at all",
                "loc": ("body",),
            }
        ]
    )

    response = calendar_conflicts_api._request_validation_error_response(exc)

    assert response.status_code == 422
    assert json.loads(response.body)["error_code"] == "calendar_correction_incoherent"


def test_request_validation_error_response_falls_back_for_unrecognized_types():
    exc = RequestValidationError(
        [{"type": "value_error", "msg": "some other failure", "loc": ("body",)}]
    )

    response = calendar_conflicts_api._request_validation_error_response(exc)

    assert json.loads(response.body)["error_code"] == "calendar_request_invalid"


@pytest.mark.asyncio
async def test_correct_judgment_404s_when_outside_caller_scope(
    dev_auth_dependency_overrides,
    monkeypatch,
):
    """A judgment_uid outside the caller's own scope must never leak as a 500 or a silent no-op."""

    async def fake_apply_correction(session, **kwargs):
        raise calendar_conflicts_api.CalendarConflictJudgmentNotFoundError(
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
                json={
                    "correction_action": "override_decision",
                    "decision_code": "available",
                    "status_code": "overridden",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
