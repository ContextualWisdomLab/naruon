"""Buyer-visible preview of recognized HWPX paragraph text.

#1373 lands ordered HWPX paragraphs in the content graph. These tests require a
read-only repository-asset preview that exposes that text in the existing Data
attachment/document surface without changing recognition semantics, calling a
model, or leaking cross-workspace assets.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import asyncpg
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import get_auth_context, get_current_user
from core.config import settings
from db.models import Attachment, Base, Document, Email
from db.session import get_db
from main import app
from services.repository_asset_preview import (
    ERROR_HWPX_RECOGNITION_FAILED,
    ERROR_HWPX_RECOGNITION_PENDING,
    ERROR_REPOSITORY_ASSET_NOT_FOUND,
    NEXT_ACTION_CHOOSE_ANOTHER_FILE,
    NEXT_ACTION_READ_RECOGNIZED_TEXT,
    NEXT_ACTION_WAIT_FOR_RECOGNITION,
    build_attachment_preview,
    build_document_preview,
)

TEST_SESSION_HMAC_SECRET = "data-quality-surface-hmac-material-32-bytes"  # noqa: S105


class MockResult:
    """Return predetermined rows for one preview lookup query."""

    def __init__(self, obj):
        self.obj = obj

    def scalars(self):
        return self

    def all(self):
        return self.obj if isinstance(self.obj, list) else []

    def __iter__(self):
        return iter(self.all())

    def scalar_one_or_none(self):
        if isinstance(self.obj, list):
            return self.obj[0] if self.obj else None
        return self.obj


class PreviewMockSession:
    """Serve document or scoped attachment rows without a live database."""

    def __init__(self, *, documents=None, attachment_rows=None):
        self.documents = list(documents or [])
        self.attachment_rows = list(attachment_rows or [])
        self.get_calls: list[tuple[object, object]] = []
        self.executed_queries: list[object] = []

    async def get(self, model, identity):
        self.get_calls.append((model, identity))
        if model is Attachment:
            for attachment, _email in self.attachment_rows:
                if getattr(attachment, "id", None) == identity:
                    return attachment
        return None

    async def execute(self, query):
        self.executed_queries.append(query)
        rendered_query = str(query).lower()
        if "workspace_documents" in rendered_query:
            compiled = query.compile()
            params = compiled.params
            document_id = next(
                (
                    value
                    for key, value in params.items()
                    if key.startswith("document_id")
                ),
                None,
            )
            workspace_id = next(
                (
                    value
                    for key, value in params.items()
                    if key.startswith("workspace_id")
                ),
                None,
            )
            rows = [
                document
                for document in self.documents
                if (document_id is None or document.document_id == document_id)
                and (workspace_id is None or document.workspace_id == workspace_id)
            ]
            return MockResult(rows[0] if rows else None)
        if "content_segments" in rendered_query:
            return MockResult([])
        return MockResult(
            [
                (getattr(attachment, "id", None), attachment.filename, email)
                for attachment, email in self.attachment_rows
            ]
        )


def _base64url_encode(data: bytes) -> str:
    """Encode JWT segments without padding."""

    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _signed_session_token(payload: dict[str, object]) -> str:
    """Sign a control-plane HMAC session for preview route tests."""

    header_segment = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        TEST_SESSION_HMAC_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _valid_session_payload(**overrides: object) -> dict[str, object]:
    """Return a member session scoped to the preview fixture workspace."""

    payload: dict[str, object] = {
        "ver": 1,
        "iss": "naruon-control-plane",
        "aud": "naruon-api",
        "sub": "admin",
        "role": "member",
        "org": "org-acme",
        "groups": ["group-data"],
        "workspace": "workspace-org-acme",
        "exp": int(time.time()) + 300,
    }
    payload.update(overrides)
    return payload


def _now() -> datetime:
    """Return a fixed UTC timestamp for fixture emails and documents."""

    return datetime(2026, 5, 28, 5, 45, tzinfo=timezone.utc)


def _email(*, message_id: str, user_id: str = "admin", organization_id: str = "org-acme") -> Email:
    """Build one scoped source email for opaque asset-key tests."""

    return Email(
        user_id=user_id,
        organization_id=organization_id,
        message_id=message_id,
        thread_id="thread-hwpx",
        fingerprint=f"sha256:{message_id}",
        sender="partner@example.com",
        recipients="owner@example.com",
        subject="HWPX source email",
        date=_now(),
        body="source email body",
    )


def _hwpx_attachment(
    *,
    parse_status: str,
    content: str,
    parse_error_code: str | None = None,
    segments: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Build one in-memory HWPX attachment for preview mapping tests."""

    return SimpleNamespace(
        filename="decision.hwpx",
        content=content,
        content_type="application/hwp+zip",
        parse_content_type="application/hwp+zip",
        parser_key="hwpx",
        parse_status=parse_status,
        parse_error_code=parse_error_code,
        content_segments=list(segments or []),
    )


def _hwpx_orm_attachment(
    *,
    parse_status: str,
    content: str,
    parse_error_code: str | None = None,
    attachment_id: int = 17,
) -> Attachment:
    """Build one mapped HWPX attachment for signed preview-route tests."""

    attachment = Attachment(
        filename="decision.hwpx",
        content=content,
        content_type="application/hwp+zip",
        parse_content_type="application/hwp+zip",
        parser_key="hwpx",
        parse_status=parse_status,
        parse_error_code=parse_error_code,
    )
    attachment.id = attachment_id
    return attachment


def _with_signed_auth(mock_db, token: str):
    """Bind a signed session and mock DB to the FastAPI app."""

    async def override_get_db():
        yield mock_db

    previous_secret = settings.AUTH_SESSION_HMAC_SECRET
    original_overrides = dict(app.dependency_overrides)
    settings.AUTH_SESSION_HMAC_SECRET = SecretStr(TEST_SESSION_HMAC_SECRET)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_auth_context, None)
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    return client, previous_secret, original_overrides


def _restore_overrides(previous_secret, original_overrides) -> None:
    """Restore FastAPI overrides and the HMAC secret after a route test."""

    settings.AUTH_SESSION_HMAC_SECRET = previous_secret
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_recognized_hwpx_preview_returns_ordered_paragraphs() -> None:
    """Parsed HWPX segments become readable ordered paragraph text."""

    attachment = _hwpx_attachment(
        parse_status="hwpx_xml_package_parsed",
        content="Quarterly decision record\n\nApprove the next action.",
        segments=[
            SimpleNamespace(ordinal_index=1, safe_text_content="Approve the next action."),
            SimpleNamespace(ordinal_index=0, safe_text_content="Quarterly decision record"),
        ],
    )

    preview = build_attachment_preview("asset_recognized_hwpx", attachment)

    assert preview.preview_state == "recognized"
    assert preview.parser_family == "hwpx"
    assert preview.paragraph_texts == (
        "Quarterly decision record",
        "Approve the next action.",
    )
    assert preview.preview_text == (
        "Quarterly decision record\n\nApprove the next action."
    )
    assert preview.next_action == NEXT_ACTION_READ_RECOGNIZED_TEXT
    assert preview.error_code is None
    assert preview.provider_write_executed is False


def test_pending_hwpx_preview_does_not_treat_retained_bytes_as_content() -> None:
    """Pending HWPX must wait; retained package bytes are not empty readable text."""

    attachment = _hwpx_attachment(
        parse_status="hwpx_xml_package_pending",
        content="UEsDBAoAAAAAAretained-hwpx-bytes",
    )

    preview = build_attachment_preview("asset_pending_hwpx", attachment)

    assert preview.preview_state == "pending"
    assert preview.parser_family == "hwpx"
    assert preview.paragraph_texts == ()
    assert preview.preview_text is None
    assert preview.next_action == NEXT_ACTION_WAIT_FOR_RECOGNITION
    assert preview.error_code == ERROR_HWPX_RECOGNITION_PENDING


def test_failed_hwpx_preview_asks_buyer_to_choose_another_file() -> None:
    """Failed HWPX stays explicit; missing text is not rendered as empty content."""

    attachment = _hwpx_attachment(
        parse_status="hwpx_xml_package_failed",
        content="",
        parse_error_code="recognition_failed",
    )

    preview = build_attachment_preview("asset_failed_hwpx", attachment)

    assert preview.preview_state == "failed"
    assert preview.parser_family == "hwpx"
    assert preview.paragraph_texts == ()
    assert preview.preview_text is None
    assert preview.next_action == NEXT_ACTION_CHOOSE_ANOTHER_FILE
    assert preview.error_code == ERROR_HWPX_RECOGNITION_FAILED


def test_recognized_hwpx_preview_uses_explicit_segments_without_relationship() -> None:
    """Preview text comes from passed segments, not a replaced relationship."""

    attachment = _hwpx_attachment(
        parse_status="hwpx_xml_package_parsed",
        content="ignored retained package bytes",
        segments=[],
    )
    segments = [
        SimpleNamespace(ordinal_index=1, safe_text_content="Approve the next action."),
        SimpleNamespace(ordinal_index=0, safe_text_content="Quarterly decision record"),
    ]

    preview = build_attachment_preview(
        "asset_recognized_hwpx",
        attachment,
        content_segments=segments,
    )

    assert attachment.content_segments == []
    assert preview.preview_state == "recognized"
    assert preview.paragraph_texts == (
        "Quarterly decision record",
        "Approve the next action.",
    )


def test_workspace_document_preview_returns_stored_text() -> None:
    """Known markdown assets such as roadmap.md remain readable through preview."""

    document = Document(
        document_id="doc_repository_ready",
        workspace_id="workspace-org-acme",
        document_name="roadmap.md",
        document_type="text/markdown",
        document_content="# Q2 roadmap\n\nShip the buyer-visible Data room.",
        document_status="uploaded",
        created_at=_now(),
    )

    preview = build_document_preview(document.document_id, document)

    assert preview.preview_state == "recognized"
    assert preview.asset_type == "workspace_document"
    assert preview.paragraph_texts == (
        "# Q2 roadmap",
        "Ship the buyer-visible Data room.",
    )
    assert preview.preview_text is not None
    assert "Q2 roadmap" in preview.preview_text
    assert preview.next_action == NEXT_ACTION_READ_RECOGNIZED_TEXT
    assert preview.error_code is None


def test_preview_route_returns_recognized_hwpx_for_scoped_attachment() -> None:
    """The signed preview route exposes scoped recognized HWPX text."""

    import api.data as data_api

    email = _email(message_id="<hwpx-ready@example.com>")
    attachment = _hwpx_orm_attachment(
        parse_status="hwpx_xml_package_parsed",
        content="Quarterly decision record\n\nApprove the next action.",
    )
    asset_key = data_api._opaque_asset_key(email, attachment)
    mock_db = PreviewMockSession(attachment_rows=[(attachment, email)])
    token = _signed_session_token(_valid_session_payload())
    client, previous_secret, original_overrides = _with_signed_auth(mock_db, token)
    try:
        response = client.get(f"/api/data/repository-assets/{asset_key}/preview")
    finally:
        client.close()
        _restore_overrides(previous_secret, original_overrides)

    assert response.status_code == 200, response.text
    assert mock_db.get_calls == [(Attachment, attachment.id)]
    data = response.json()
    assert data["asset_key"] == asset_key
    assert data["preview_state"] == "recognized"
    assert data["paragraph_texts"] == [
        "Quarterly decision record",
        "Approve the next action.",
    ]
    assert data["error_code"] is None
    assert data["next_action"] == NEXT_ACTION_READ_RECOGNIZED_TEXT
    assert data["provider_write_executed"] is False


def test_preview_route_loads_only_the_matched_attachment_payload() -> None:
    """First-pass preview lookup stays lightweight and loads only the matched row."""

    import api.data as data_api

    email = _email(message_id="<hwpx-ready@example.com>")
    matched = _hwpx_orm_attachment(
        parse_status="hwpx_xml_package_parsed",
        content="Quarterly decision record\n\nApprove the next action.",
        attachment_id=17,
    )
    sibling = _hwpx_orm_attachment(
        parse_status="hwpx_xml_package_parsed",
        content="S" * 8192,
        attachment_id=18,
    )
    sibling.filename = "other-notes.hwpx"
    asset_key = data_api._opaque_asset_key(email, matched)
    mock_db = PreviewMockSession(attachment_rows=[(sibling, email), (matched, email)])
    token = _signed_session_token(_valid_session_payload())
    client, previous_secret, original_overrides = _with_signed_auth(mock_db, token)
    try:
        response = client.get(f"/api/data/repository-assets/{asset_key}/preview")
    finally:
        client.close()
        _restore_overrides(previous_secret, original_overrides)

    assert response.status_code == 200, response.text
    assert mock_db.get_calls == [(Attachment, matched.id)]
    candidate_queries = [
        query
        for query in mock_db.executed_queries
        if "content_segments" not in str(query).lower()
        and "workspace_documents" not in str(query).lower()
    ]
    assert candidate_queries
    candidate_columns = {
        str(column.get("name"))
        for column in candidate_queries[0].column_descriptions
    }
    assert "content" not in candidate_columns
    assert "filename" in candidate_columns
    assert "id" in candidate_columns
    assert response.json()["paragraph_texts"] == [
        "Quarterly decision record",
        "Approve the next action.",
    ]


@pytest.mark.parametrize(
    ("foreign_kwargs", "asset_key"),
    [
        ({}, "asset_missing_preview_key"),
        (
            {"user_id": "rival", "organization_id": "org-rival"},
            None,
        ),
    ],
)
def test_preview_route_hides_unknown_and_cross_workspace_assets(
    foreign_kwargs: dict[str, str],
    asset_key: str | None,
) -> None:
    """Unknown and cross-workspace assets both 404 as repository_asset_not_found."""

    import api.data as data_api

    email = _email(message_id="<hwpx-foreign@example.com>", **foreign_kwargs)
    attachment = _hwpx_orm_attachment(
        parse_status="hwpx_xml_package_parsed",
        content="Secret rival paragraph",
    )
    requested_key = asset_key or data_api._opaque_asset_key(email, attachment)
    mock_db = PreviewMockSession(
        documents=[
            Document(
                document_id="doc_other_workspace",
                workspace_id="workspace-org-rival",
                document_name="secret.md",
                document_type="text/markdown",
                document_content="cross workspace secret",
                document_status="uploaded",
                created_at=_now(),
            )
        ],
        attachment_rows=[] if asset_key else [(attachment, email)],
    )
    token = _signed_session_token(_valid_session_payload())
    client, previous_secret, original_overrides = _with_signed_auth(mock_db, token)
    try:
        response = client.get(f"/api/data/repository-assets/{requested_key}/preview")
        other_workspace = client.get(
            "/api/data/repository-assets/doc_other_workspace/preview"
        )
    finally:
        client.close()
        _restore_overrides(previous_secret, original_overrides)

    assert response.status_code == 404, response.text
    assert response.json()["detail"]["error_code"] == ERROR_REPOSITORY_ASSET_NOT_FOUND
    assert "Secret rival paragraph" not in response.text
    assert other_workspace.status_code == 404
    assert (
        other_workspace.json()["detail"]["error_code"]
        == ERROR_REPOSITORY_ASSET_NOT_FOUND
    )
    assert "cross workspace secret" not in other_workspace.text


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_repository_asset_preview_postgres_smoke_scopes_hwpx_text() -> None:
    """Recognized HWPX preview is readable; rival workspace text stays hidden."""

    database_url = getattr(settings, "DATABASE_URL", None)
    if not database_url:
        pytest.skip("PostgreSQL smoke path unavailable: DATABASE_URL is not set")

    user_id = f"preview_smoke_user_{uuid.uuid4().hex[:12]}"
    organization_id = f"preview_smoke_org_{uuid.uuid4().hex[:12]}"
    workspace_id = f"workspace_{organization_id}"
    rival_user_id = f"preview_rival_user_{uuid.uuid4().hex[:12]}"
    rival_organization_id = f"preview_rival_org_{uuid.uuid4().hex[:12]}"
    message_id = f"<preview-hwpx-{uuid.uuid4().hex}@example.com>"
    rival_message_id = f"<preview-rival-{uuid.uuid4().hex}@example.com>"
    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            owner_email = await conn.execute(
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
                    "thread_id": "thread-preview-hwpx",
                    "fingerprint": f"sha256:{message_id}",
                    "sender": "partner@example.com",
                    "recipients": "owner@example.com",
                    "subject": "HWPX preview smoke",
                    "body": "source email body",
                },
            )
            rival_email = await conn.execute(
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
                    "user_id": rival_user_id,
                    "organization_id": rival_organization_id,
                    "message_id": rival_message_id,
                    "thread_id": "thread-preview-rival",
                    "fingerprint": f"sha256:{rival_message_id}",
                    "sender": "rival@example.com",
                    "recipients": "rival@example.com",
                    "subject": "Rival HWPX",
                    "body": "rival body",
                },
            )
            owner_email_id = owner_email.scalar_one()
            rival_email_id = rival_email.scalar_one()
            await conn.execute(
                text(
                    """
                    INSERT INTO email_attachments (
                        email_id, filename, content,
                        content_type, parse_status, parse_content_type,
                        parser_key, parse_error_code
                    )
                    VALUES
                    (
                        CAST(:owner_email_id AS INTEGER), 'decision.hwpx',
                        :owner_content, 'application/hwp+zip',
                        'hwpx_xml_package_parsed', 'application/hwp+zip',
                        'hwpx', NULL
                    ),
                    (
                        CAST(:rival_email_id AS INTEGER), 'secret.hwpx',
                        :rival_content, 'application/hwp+zip',
                        'hwpx_xml_package_parsed', 'application/hwp+zip',
                        'hwpx', NULL
                    )
                    """
                ),
                {
                    "owner_email_id": owner_email_id,
                    "rival_email_id": rival_email_id,
                    "owner_content": (
                        "Quarterly decision record\n\nApprove the next action."
                    ),
                    "rival_content": "Secret rival paragraph",
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

    previous_secret = settings.AUTH_SESSION_HMAC_SECRET
    original_overrides = dict(app.dependency_overrides)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def override_real_db():
            async with session_factory() as session:
                yield session

        import api.data as data_api

        owner_email = _email(
            message_id=message_id,
            user_id=user_id,
            organization_id=organization_id,
        )
        owner_attachment = _hwpx_orm_attachment(
            parse_status="hwpx_xml_package_parsed",
            content="Quarterly decision record\n\nApprove the next action.",
        )
        rival_email = _email(
            message_id=rival_message_id,
            user_id=rival_user_id,
            organization_id=rival_organization_id,
        )
        rival_attachment = _hwpx_orm_attachment(
            parse_status="hwpx_xml_package_parsed",
            content="Secret rival paragraph",
        )
        rival_attachment.filename = "secret.hwpx"
        owner_key = data_api._opaque_asset_key(owner_email, owner_attachment)
        rival_key = data_api._opaque_asset_key(rival_email, rival_attachment)

        settings.AUTH_SESSION_HMAC_SECRET = SecretStr(TEST_SESSION_HMAC_SECRET)
        token = _signed_session_token(
            _valid_session_payload(
                sub=user_id,
                org=organization_id,
                workspace=workspace_id,
            )
        )
        app.dependency_overrides[get_db] = override_real_db
        app.dependency_overrides.pop(get_auth_context, None)
        app.dependency_overrides.pop(get_current_user, None)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            recognized = await client.get(
                f"/api/data/repository-assets/{owner_key}/preview"
            )
            hidden = await client.get(
                f"/api/data/repository-assets/{rival_key}/preview"
            )
            missing = await client.get(
                "/api/data/repository-assets/asset_missing_preview_key/preview"
            )
    finally:
        settings.AUTH_SESSION_HMAC_SECRET = previous_secret
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    DELETE FROM email_attachments
                    WHERE email_id IN (
                        SELECT id FROM email_records
                        WHERE user_id IN (:user_id, :rival_user_id)
                    )
                    """
                ),
                {"user_id": user_id, "rival_user_id": rival_user_id},
            )
            await conn.execute(
                text(
                    "DELETE FROM email_records WHERE user_id IN (:user_id, :rival_user_id)"
                ),
                {"user_id": user_id, "rival_user_id": rival_user_id},
            )
        await engine.dispose()

    assert recognized.status_code == 200, recognized.text
    recognized_body = recognized.json()
    assert recognized_body["preview_state"] == "recognized"
    assert recognized_body["paragraph_texts"] == [
        "Quarterly decision record",
        "Approve the next action.",
    ]
    assert hidden.status_code == 404
    assert hidden.json()["detail"]["error_code"] == ERROR_REPOSITORY_ASSET_NOT_FOUND
    assert "Secret rival paragraph" not in hidden.text
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == ERROR_REPOSITORY_ASSET_NOT_FOUND
