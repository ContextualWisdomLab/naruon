"""Real PostgreSQL acceptance for document endpoint workspace authorization."""

import secrets
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import AuthContext
from api.data import (
    DataDocumentUploadRequest,
    reparse_data_document,
    upload_data_document,
)
from core.config import settings

pytestmark = pytest.mark.postgres

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_migrations(database_url: str) -> None:
    """Apply the managed migration path to an isolated PostgreSQL database."""

    result = subprocess.run(
        [sys.executable, str(_BACKEND_ROOT / "scripts" / "migrate_db.py"), "head"],
        cwd=_BACKEND_ROOT,
        env={
            "DATABASE_URL": database_url,
            "AUTH_SESSION_HMAC_SECRET": secrets.token_urlsafe(48),
        },
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert not any(
        status in output for status in ("Timeout", "Fatal", "Warn", "Denied")
    ), output


@pytest_asyncio.fixture
async def document_scope_database_url():
    """Create an isolated database; unavailable PostgreSQL is an acceptance failure."""

    base_url = make_url(settings.DATABASE_URL)
    database_name = f"test_document_scope_{uuid.uuid4().hex[:12]}"

    async def admin(sql: str) -> None:
        connection = await asyncpg.connect(
            host=base_url.host,
            port=base_url.port,
            user=base_url.username,
            password=base_url.password,
            database="postgres",
        )
        try:
            await connection.execute(sql)
        finally:
            await connection.close()

    try:
        await admin(f'CREATE DATABASE "{database_name}"')
    except Exception as exc:
        pytest.fail(
            f"PostgreSQL is required for document endpoint acceptance: {exc}",
            pytrace=False,
        )

    database_url = base_url.set(database=database_name).render_as_string(
        hide_password=False
    )
    try:
        _run_migrations(database_url)
        yield database_url
    finally:
        try:
            await admin(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        except Exception as exc:
            pytest.fail(
                f"PostgreSQL cleanup failed for document endpoint acceptance: {exc}",
                pytrace=False,
            )


def _auth(
    *,
    user_id: str,
    organization_id: str | None,
    workspace_id: str,
    session_verifier: str,
) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id=workspace_id,
        session_verifier=session_verifier,
    )


async def _workspace_binding(
    database_url: str,
    workspace_id: str,
) -> tuple[str | None, str | None] | None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT organization_id, owner_user_id FROM workspace_entities "
                    "WHERE workspace_id = :workspace_id"
                ),
                {"workspace_id": workspace_id},
            )
            row = result.one_or_none()
            if row is None:
                return None
            return row.organization_id, row.owner_user_id
    finally:
        await engine.dispose()


async def _document_count(database_url: str, workspace_id: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT count(*) FROM workspace_documents "
                    "WHERE workspace_id = :workspace_id"
                ),
                {"workspace_id": workspace_id},
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trusted_organization_upload_binds_workspace_and_rejects_other_org(
    document_scope_database_url,
) -> None:
    """One opaque workspace cannot accept document writes from two organizations."""

    engine = create_async_engine(document_scope_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = "opaque-org-endpoint-7f3c"
    request = DataDocumentUploadRequest(
        document_name="evidence.md",
        document_type="text/markdown",
        document_content="source-backed evidence",
    )
    try:
        async with session_factory() as session:
            response = await upload_data_document(
                request=request,
                auth_context=_auth(
                    user_id="member-a",
                    organization_id="org-acme",
                    workspace_id=workspace_id,
                    session_verifier="oidc",
                ),
                db=session,
            )
            assert response.workspace_id == workspace_id

        assert await _workspace_binding(
            document_scope_database_url,
            workspace_id,
        ) == ("org-acme", None)
        assert await _document_count(document_scope_database_url, workspace_id) == 1

        async with session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await upload_data_document(
                    request=request,
                    auth_context=_auth(
                        user_id="member-b",
                        organization_id="org-other",
                        workspace_id=workspace_id,
                        session_verifier="oidc",
                    ),
                    db=session,
                )
        assert exc_info.value.status_code == 403
        assert await _workspace_binding(
            document_scope_database_url,
            workspace_id,
        ) == ("org-acme", None)
        assert await _document_count(document_scope_database_url, workspace_id) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_hmac_cannot_establish_unbound_document_workspace(
    document_scope_database_url,
) -> None:
    """A signed compatibility session cannot turn an opaque claim into ownership."""

    engine = create_async_engine(document_scope_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = "opaque-hmac-endpoint-unbound-4a2b"
    try:
        async with session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await upload_data_document(
                    request=DataDocumentUploadRequest(
                        document_name="blocked.md",
                        document_type="text/markdown",
                        document_content="must not persist",
                    ),
                    auth_context=_auth(
                        user_id="member-hmac",
                        organization_id="org-acme",
                        workspace_id=workspace_id,
                        session_verifier="hmac",
                    ),
                    db=session,
                )
        assert exc_info.value.status_code == 403
        assert await _workspace_binding(document_scope_database_url, workspace_id) is None
        assert await _document_count(document_scope_database_url, workspace_id) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trusted_personal_upload_binds_owner_and_rejects_other_user(
    document_scope_database_url,
) -> None:
    """Personal opaque workspaces persist one user owner rather than identifier shape."""

    engine = create_async_engine(document_scope_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = "opaque-personal-endpoint-91d0"
    request = DataDocumentUploadRequest(
        document_name="personal.md",
        document_type="text/markdown",
        document_content="personal evidence",
    )
    try:
        async with session_factory() as session:
            await upload_data_document(
                request=request,
                auth_context=_auth(
                    user_id="member-personal-a",
                    organization_id=None,
                    workspace_id=workspace_id,
                    session_verifier="server",
                ),
                db=session,
            )

        assert await _workspace_binding(
            document_scope_database_url,
            workspace_id,
        ) == (None, "member-personal-a")

        async with session_factory() as session:
            with pytest.raises(HTTPException) as exc_info:
                await upload_data_document(
                    request=request,
                    auth_context=_auth(
                        user_id="member-personal-b",
                        organization_id=None,
                        workspace_id=workspace_id,
                        session_verifier="server",
                    ),
                    db=session,
                )
        assert exc_info.value.status_code == 403
        assert await _document_count(document_scope_database_url, workspace_id) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_historical_null_document_requires_correlated_registry_owner(
    document_scope_database_url,
) -> None:
    """Legacy NULL organization rows are readable only through the bound registry row."""

    engine = create_async_engine(document_scope_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    org_workspace = "opaque-org-legacy-document-a6e1"
    personal_workspace = "opaque-personal-legacy-document-f3b9"
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO workspace_entities "
                    "(workspace_id, workspace_name, organization_id, owner_user_id, created_at) "
                    "VALUES "
                    "(:org_workspace, :org_workspace, 'org-acme', NULL, now()), "
                    "(:personal_workspace, :personal_workspace, NULL, 'member-a', now())"
                ),
                {
                    "org_workspace": org_workspace,
                    "personal_workspace": personal_workspace,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_documents "
                    "(document_id, workspace_id, organization_id, document_name, document_type, "
                    " document_content, document_status, created_at) VALUES "
                    "('legacy-org-doc', :org_workspace, NULL, 'legacy-org', 'text/plain', "
                    " 'org legacy text', 'uploaded', now()), "
                    "('legacy-personal-doc', :personal_workspace, NULL, 'legacy-personal', "
                    " 'text/plain', 'personal legacy text', 'uploaded', now())"
                ),
                {
                    "org_workspace": org_workspace,
                    "personal_workspace": personal_workspace,
                },
            )

        async with session_factory() as session:
            response = await reparse_data_document(
                document_id="legacy-org-doc",
                auth_context=_auth(
                    user_id="member-a",
                    organization_id="org-acme",
                    workspace_id=org_workspace,
                    session_verifier="hmac",
                ),
                db=session,
            )
            assert response.document_id == "legacy-org-doc"

        async with session_factory() as session:
            with pytest.raises(HTTPException) as org_exc:
                await reparse_data_document(
                    document_id="legacy-org-doc",
                    auth_context=_auth(
                        user_id="member-b",
                        organization_id="org-other",
                        workspace_id=org_workspace,
                        session_verifier="oidc",
                    ),
                    db=session,
                )
            assert org_exc.value.status_code == 404

        async with session_factory() as session:
            response = await reparse_data_document(
                document_id="legacy-personal-doc",
                auth_context=_auth(
                    user_id="member-a",
                    organization_id=None,
                    workspace_id=personal_workspace,
                    session_verifier="hmac",
                ),
                db=session,
            )
            assert response.document_id == "legacy-personal-doc"

        async with session_factory() as session:
            with pytest.raises(HTTPException) as user_exc:
                await reparse_data_document(
                    document_id="legacy-personal-doc",
                    auth_context=_auth(
                        user_id="member-b",
                        organization_id=None,
                        workspace_id=personal_workspace,
                        session_verifier="server",
                    ),
                    db=session,
                )
            assert user_exc.value.status_code == 404
    finally:
        await engine.dispose()
