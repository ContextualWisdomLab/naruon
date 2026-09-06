"""Signed-session coverage for mail attachment metadata endpoints."""

from __future__ import annotations

import datetime
import time

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.auth import SESSION_AUDIENCE, SESSION_ISSUER
from core.config import settings
from db.models import Attachment, Email
from db.session import get_db
from main import app


class _SignedMailMockSession:
    """Return one tenant-scoped email while authentication stays production-real."""

    def __init__(self, email: Email):
        self.email = email

    async def execute(self, query, params=None):
        class _MockResult:
            def __init__(self, email: Email):
                self.email = email

            def scalar_one_or_none(self):
                return self.email

            def scalars(self):
                return self

            def all(self):
                return [self.email]

        return _MockResult(self.email)


def _signed_mail_email() -> Email:
    email = Email(
        id=51,
        user_id="signed-mail-user",
        organization_id="org-signed-mail",
        message_id="<signed-mail-preview@example.com>",
        thread_id="thread-signed-mail-preview",
        sender="partner@example.com",
        recipients="owner@example.com",
        subject="Signed HWPX preview",
        date=datetime.datetime.now(datetime.timezone.utc),
        body="Open the recognized attachment.",
    )
    email.attachments = [
        Attachment(
            id=151,
            email_id=51,
            filename="decision.hwpx",
            parser_key="hwpx",
        )
    ]
    return email


def _signed_session_token() -> str:
    configured_secret = settings.AUTH_SESSION_HMAC_SECRET
    assert configured_secret is not None
    now = int(time.time())
    return jwt.encode(
        {
            "ver": 1,
            "iss": SESSION_ISSUER,
            "aud": SESSION_AUDIENCE,
            "iat": now,
            "exp": now + 600,
            "sub": "signed-mail-user",
            "role": "member",
            "org": "org-signed-mail",
            "groups": [],
            "workspace": "workspace-org-signed-mail",
        },
        configured_secret.get_secret_value(),
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def override_mail_db():
    email = _signed_mail_email()
    app.dependency_overrides[get_db] = lambda: _SignedMailMockSession(email)
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_email_attachment_detail_uses_real_signed_bearer_session(
    client: AsyncClient,
) -> None:
    """A valid HMAC bearer session authorizes attachment metadata without identity headers."""

    response = await client.get(
        "/api/emails/51",
        headers={"Authorization": f"Bearer {_signed_session_token()}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == 51
    assert payload["attachments"] == [
        {
            "asset_key": payload["attachments"][0]["asset_key"],
            "file_name": "decision.hwpx",
            "parser_family": "hwpx",
        }
    ]
    assert payload["attachments"][0]["asset_key"].startswith("asset_")


@pytest.mark.asyncio
async def test_email_attachment_detail_rejects_public_identity_headers_without_session(
    client: AsyncClient,
) -> None:
    """Public identity headers cannot substitute for the signed bearer session."""

    response = await client.get(
        "/api/emails/51",
        headers={
            "X-User-Id": "signed-mail-user",
            "X-Organization-Id": "org-signed-mail",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
