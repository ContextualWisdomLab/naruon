"""Authenticated read API for persisted email media quarantine records."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.auth import AuthContext
from db.models import Email
from db.session import get_db
from main import app
from services.email_media_quarantine_read import (
    TRACKING_PIXEL_NEXT_ACTION,
    UNSUPPORTED_MEDIA_NEXT_ACTION,
    UNRESOLVED_CID_NEXT_ACTION,
)


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


class _MediaQuarantineSession:
    """Return owner-scoped email rows or persisted quarantine rows by table."""

    def __init__(self, emails: list[Email], quarantine_rows: list[object]) -> None:
        self.emails = emails
        self.quarantine_rows = quarantine_rows
        self.queries: list[object] = []

    async def execute(self, query, params=None):
        self.queries.append(query)
        query_text = str(query).lower()

        class Result:
            def __init__(self, rows: list[object]) -> None:
                self.rows = rows

            def scalars(self):
                return self

            def all(self):
                return self.rows

            def scalar_one_or_none(self):
                return self.rows[0] if self.rows else None

        if "email_media_quarantine_records" in query_text:
            return Result(self.quarantine_rows)
        return Result(self.emails)


def _sample_email() -> Email:
    return Email(
        id=31,
        user_id="testuser",
        organization_id="org-acme",
        message_id="<quarantine-ui@example.com>",
        thread_id="thread-quarantine",
        sender="sender@example.com",
        recipients="user@example.com",
        subject="Inline media withheld",
        date=datetime.datetime(2026, 8, 17, 10, 0, tzinfo=datetime.timezone.utc),
        body="Message body without withheld bytes",
    )


def _quarantine_row(error_code: str, content_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        quarantine_record_id=7,
        message_record_id=31,
        source_part_index=1,
        content_id_value=content_id,
        source_bytes_sha256="b" * 64,
        admission_error_code=error_code,
        evidence_boundary_label="known",
        created_at=datetime.datetime(2026, 8, 17, 10, 0, tzinfo=datetime.timezone.utc),
    )


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        headers={"X-User-Id": "testuser", "X-Organization-Id": "org-acme"},
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_media_quarantine_requires_auth(client: AsyncClient) -> None:
    response = await client.get(
        "/api/emails/31/media-quarantine",
        headers={"X-User-Id": ""},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_media_quarantine_returns_three_buyer_next_actions(
    client: AsyncClient,
) -> None:
    session = _MediaQuarantineSession(
        [_sample_email()],
        [
            _quarantine_row("tracking_pixel", "open-pixel@naruon.test"),
            _quarantine_row("unsupported_media", "vector@naruon.test"),
            _quarantine_row("unresolved_cid_reference", "missing@naruon.test"),
        ],
    )
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = await client.get("/api/emails/31/media-quarantine")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert [row["admission_error_code"] for row in payload["quarantine_records"]] == [
        "tracking_pixel",
        "unsupported_media",
        "unresolved_cid_reference",
    ]
    assert [row["customer_next_action"] for row in payload["quarantine_records"]] == [
        TRACKING_PIXEL_NEXT_ACTION,
        UNSUPPORTED_MEDIA_NEXT_ACTION,
        UNRESOLVED_CID_NEXT_ACTION,
    ]
    assert "quarantine_record_id" not in payload["quarantine_records"][0]
    assert "payload_bytes" not in payload["quarantine_records"][0]
    assert "source_bytes" not in payload["quarantine_records"][0]


@pytest.mark.asyncio
async def test_media_quarantine_empty_list_is_fail_closed(
    client: AsyncClient,
) -> None:
    session = _MediaQuarantineSession([_sample_email()], [])
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = await client.get("/api/emails/31/media-quarantine")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {"quarantine_records": []}


@pytest.mark.asyncio
async def test_media_quarantine_missing_email_uses_stable_error_envelope(
    client: AsyncClient,
) -> None:
    session = _MediaQuarantineSession([], [])
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = await client.get("/api/emails/31/media-quarantine")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error_code"] == "email_not_found"
    assert detail["detail"] == "Email not found"


@pytest.mark.asyncio
async def test_media_quarantine_applies_signed_session_dependency(
    client: AsyncClient,
) -> None:
    from api.emails import get_auth_context as emails_get_auth_context

    calls: list[str] = []

    async def auth_override() -> AuthContext:
        calls.append("hit")
        return AuthContext(
            user_id="testuser",
            role="member",
            organization_id="org-acme",
            group_ids=(),
            workspace_id="workspace-org-acme",
        )

    session = _MediaQuarantineSession([_sample_email()], [])
    app.dependency_overrides[emails_get_auth_context] = auth_override
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = await client.get("/api/emails/31/media-quarantine")
    finally:
        app.dependency_overrides.pop(emails_get_auth_context, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert calls == ["hit"]
