"""Mail-detail attachments must open the existing read-only HWPX preview.

#1404 already exposes recognized ordered paragraphs at
``/api/data/repository-assets/{asset_key}/preview``. These tests require the
core mail attachment experience to list the current email's files with that
same opaque ``asset_key`` so a buyer can open HWPX text without going through
the Data repository list. Preview recognition semantics stay unchanged.
"""

from __future__ import annotations

import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db.models import Attachment, Email
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


class _EmailDetailMockSession:
    """Return one email row for mail-detail attachment listing tests."""

    def __init__(self, items: list[Email]):
        self.items = items

    async def execute(self, query, params=None):
        class _MockResult:
            def __init__(self, rows):
                self.rows = rows

            def scalars(self):
                return self

            def all(self):
                return self.rows

            def scalar_one_or_none(self):
                return self.rows[0] if self.rows else None

        return _MockResult(self.items)


def _hwpx_mail_email() -> Email:
    """Build one scoped email that already has a recognized HWPX attachment."""

    email = Email(
        id=41,
        user_id="testuser",
        organization_id="org-acme",
        message_id="<mail-hwpx@example.com>",
        thread_id="thread-mail-hwpx",
        sender="partner@example.com",
        reply_to="partner@example.com",
        recipients="user@example.com",
        subject="HWPX decision record",
        date=datetime.datetime.now(datetime.timezone.utc),
        body="Please review the attached HWPX decision record.",
    )
    email.attachments = [
        Attachment(
            id=99,
            email_id=41,
            filename="<script>alert(1)</script>decision.hwpx",
            content="Quarterly decision record\n\nApprove the next action.",
            content_type="application/hwp+zip",
            parse_status="hwpx_xml_package_parsed",
            parse_content_type="application/hwp+zip",
            parser_key="hwpx",
        )
    ]
    return email


@pytest.fixture
def mail_hwpx_email() -> Email:
    """Provide the recognized HWPX mail fixture to route tests."""

    return _hwpx_mail_email()


@pytest.fixture
def db_session(mail_hwpx_email: Email) -> _EmailDetailMockSession:
    """Bind the mail-detail mock session to the recognized HWPX email."""

    return _EmailDetailMockSession([mail_hwpx_email])


@pytest.fixture(autouse=True)
def override_get_db(db_session: _EmailDetailMockSession):
    """Install the mail-detail mock database for this module."""

    from db.session import get_db

    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client():
    """Return a signed-session test client scoped to the fixture owner."""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        headers={
            "X-User-Id": "testuser",
            "X-Organization-Id": "org-acme",
        },
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_email_detail_lists_opaque_hwpx_attachment_refs(
    client: AsyncClient,
    mail_hwpx_email: Email,
) -> None:
    """Mail detail exposes the current email's HWPX file without sequential ids."""

    import api.data as data_api

    response = await client.get(f"/api/emails/{mail_hwpx_email.id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    attachments = payload["attachments"]
    assert len(attachments) == 1
    attachment = attachments[0]
    expected_key = data_api._opaque_asset_key(
        mail_hwpx_email,
        mail_hwpx_email.attachments[0],
    )
    assert attachment["asset_key"] == expected_key
    assert attachment["asset_key"].startswith("asset_")
    assert attachment["file_name"] == "decision.hwpx"
    assert attachment["parser_family"] == "hwpx"
    assert "id" not in attachment
    assert "email_id" not in attachment
    assert "content" not in attachment
    assert "<script" not in attachment["file_name"].lower()
    assert "alert(1)" not in attachment["file_name"]


@pytest.mark.asyncio
async def test_email_thread_lists_the_same_opaque_attachment_refs(
    client: AsyncClient,
    mail_hwpx_email: Email,
) -> None:
    """Thread messages keep the same opaque attachment keys as mail detail."""

    import api.data as data_api

    response = await client.get(
        f"/api/emails/thread/{mail_hwpx_email.thread_id}"
    )

    assert response.status_code == 200, response.text
    items = response.json()["thread"]
    assert len(items) == 1
    attachment = items[0]["attachments"][0]
    assert attachment["asset_key"] == data_api._opaque_asset_key(
        mail_hwpx_email,
        mail_hwpx_email.attachments[0],
    )
    assert attachment["file_name"] == "decision.hwpx"
    assert "id" not in attachment


@pytest.mark.asyncio
async def test_email_detail_without_attachments_returns_empty_list(
    client: AsyncClient,
) -> None:
    """Missing attachments stay an empty list, never implied empty document text."""

    from db.session import get_db

    bare_email = Email(
        id=42,
        user_id="testuser",
        organization_id="org-acme",
        message_id="<mail-no-attach@example.com>",
        thread_id="thread-mail-empty",
        sender="partner@example.com",
        recipients="user@example.com",
        subject="No attachments",
        date=datetime.datetime.now(datetime.timezone.utc),
        body="There is no attached file.",
    )
    app.dependency_overrides[get_db] = lambda: _EmailDetailMockSession([bare_email])

    response = await client.get(f"/api/emails/{bare_email.id}")

    assert response.status_code == 200, response.text
    assert response.json()["attachments"] == []


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_email_detail_preview_postgres_smoke_lists_opaque_hwpx_key() -> None:
    """Mail detail returns the same opaque key without loading attachment bodies."""

    import uuid

    import asyncpg
    from sqlalchemy import event, text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.config import settings
    from db.models import Base
    from db.session import get_db

    database_url = getattr(settings, "DATABASE_URL", None)
    if not database_url:
        pytest.skip("PostgreSQL smoke path unavailable: DATABASE_URL is not set")

    user_id = f"mail_preview_user_{uuid.uuid4().hex[:12]}"
    organization_id = f"mail_preview_org_{uuid.uuid4().hex[:12]}"
    message_id = f"<mail-preview-{uuid.uuid4().hex}@example.com>"
    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            inserted = await conn.execute(
                text(
                    """
                    INSERT INTO email_records (
                        user_id, organization_id, message_id, thread_id,
                        fingerprint, sender, recipients, subject, "date", body
                    )
                    VALUES (
                        :user_id, :organization_id, :message_id, :thread_id,
                        :fingerprint, :sender, :recipients, :subject, now(), :body
                    )
                    RETURNING id
                    """
                ),
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "message_id": message_id,
                    "thread_id": "thread-mail-preview-hwpx",
                    "fingerprint": f"sha256:{message_id}",
                    "sender": "partner@example.com",
                    "recipients": "owner@example.com",
                    "subject": "Mail HWPX preview smoke",
                    "body": "source email body",
                },
            )
            email_id = inserted.scalar_one()
            await conn.execute(
                text(
                    """
                    INSERT INTO email_attachments (
                        email_id, filename, content,
                        content_type, parse_status, parse_content_type,
                        parser_key, parse_error_code
                    )
                    VALUES (
                        CAST(:email_id AS INTEGER), 'decision.hwpx',
                        :content, 'application/hwp+zip',
                        'hwpx_xml_package_parsed', 'application/hwp+zip',
                        'hwpx', NULL
                    )
                    """
                ),
                {
                    "email_id": email_id,
                    "content": (
                        "Quarterly decision record\n\nApprove the next action."
                    ),
                },
            )
    except (
        ConnectionRefusedError,
        OSError,
        OperationalError,
        asyncpg.CannotConnectNowError,
        asyncpg.InvalidAuthorizationSpecificationError,
        asyncpg.InvalidCatalogNameError,
        asyncpg.InvalidPasswordError,
    ):
        await engine.dispose()
        pytest.skip("PostgreSQL smoke path unavailable")
    except Exception:
        await engine.dispose()
        raise

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_real_db():
        async with session_factory() as session:
            yield session

    import api.data as data_api

    expected_key = data_api._opaque_asset_key(
        Email(
            user_id=user_id,
            organization_id=organization_id,
            message_id=message_id,
        ),
        Attachment(filename="decision.hwpx"),
    )
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_real_db
    attachment_selects: list[str] = []

    def capture_attachment_select(
        _conn, _cursor, statement: str, _parameters, _context, _executemany
    ) -> None:
        if "from email_attachments" in statement.lower().replace('"', ""):
            attachment_selects.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_attachment_select)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            headers={
                "X-User-Id": user_id,
                "X-Organization-Id": organization_id,
            },
            base_url="http://test",
        ) as real_client:
            detail = await real_client.get(f"/api/emails/{email_id}")
            detail_attachment_selects = tuple(attachment_selects)
            attachment_selects.clear()
            thread = await real_client.get(
                "/api/emails/thread/thread-mail-preview-hwpx"
            )
            thread_attachment_selects = tuple(attachment_selects)
            attachment_selects.clear()
            preview = await real_client.get(
                f"/api/data/repository-assets/{expected_key}/preview"
            )
            hidden = await real_client.get(
                "/api/data/repository-assets/asset_missing_mail_preview/preview"
            )
    finally:
        event.remove(
            engine.sync_engine, "before_cursor_execute", capture_attachment_select
        )
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        async with engine.begin() as cleanup_conn:
            await cleanup_conn.execute(
                text("DELETE FROM email_attachments WHERE email_id = :email_id"),
                {"email_id": email_id},
            )
            await cleanup_conn.execute(
                text("DELETE FROM email_records WHERE id = :email_id"),
                {"email_id": email_id},
            )
        await engine.dispose()

    assert detail.status_code == 200, detail.text
    attachments = detail.json()["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["asset_key"] == expected_key
    assert attachments[0]["file_name"] == "decision.hwpx"
    assert "id" not in attachments[0]
    assert thread.status_code == 200, thread.text
    assert len(thread.json()["thread"]) == 1
    assert detail_attachment_selects
    assert thread_attachment_selects
    for statement in (*detail_attachment_selects, *thread_attachment_selects):
        normalized_statement = statement.lower().replace('"', "")
        assert "email_attachments.content" not in normalized_statement
    assert preview.status_code == 200, preview.text
    assert preview.json()["preview_state"] == "recognized"
    assert preview.json()["paragraph_texts"] == [
        "Quarterly decision record",
        "Approve the next action.",
    ]
    assert hidden.status_code == 404
    assert hidden.json()["detail"]["error_code"] == "repository_asset_not_found"
