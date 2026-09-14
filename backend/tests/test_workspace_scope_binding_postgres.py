"""Real PostgreSQL acceptance for server-side workspace organization binding."""

import asyncio
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from services.workspace_scope import (
    WorkspaceOrganizationBindingRequired,
    WorkspaceOrganizationConflict,
    get_or_create_bound_workspace,
)

pytestmark = pytest.mark.postgres

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_migrations(database_url: str) -> None:
    """Apply the managed migration path with only required bootstrap settings."""

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
async def binding_database_url():
    """Create an isolated database; unavailable PostgreSQL is an acceptance failure."""

    base_url = make_url(settings.DATABASE_URL)
    database_name = f"test_workspace_scope_{uuid.uuid4().hex[:12]}"

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
            f"PostgreSQL is required for workspace binding acceptance: {exc}",
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
                f"PostgreSQL cleanup failed for workspace binding acceptance: {exc}",
                pytrace=False,
            )


async def _read_binding(database_url: str, workspace_id: str) -> str | None:
    """Read the persisted binding independently of the service session."""

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT organization_id FROM workspace_entities "
                    "WHERE workspace_id = :workspace_id"
                ),
                {"workspace_id": workspace_id},
            )
            return result.scalar_one_or_none()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_binding_requires_trusted_establishment_and_rejects_mismatch(
    binding_database_url,
) -> None:
    """HMAC may consume existing evidence but cannot create or change ownership."""

    engine = create_async_engine(binding_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            with pytest.raises(WorkspaceOrganizationBindingRequired):
                async with session.begin():
                    await get_or_create_bound_workspace(
                        session,
                        "opaque-hmac-unbound-1",
                        "org-acme",
                        session_verifier="hmac",
                    )

        assert await _read_binding(binding_database_url, "opaque-hmac-unbound-1") is None

        async with session_factory() as session:
            async with session.begin():
                created = await get_or_create_bound_workspace(
                    session,
                    "opaque-trusted-7f3c",
                    "org-acme",
                    session_verifier="override",
                )
                assert created.workspace_id == "opaque-trusted-7f3c"

        assert await _read_binding(binding_database_url, "opaque-trusted-7f3c") == "org-acme"

        async with session_factory() as session:
            async with session.begin():
                reused = await get_or_create_bound_workspace(
                    session,
                    "opaque-trusted-7f3c",
                    "org-acme",
                    session_verifier="hmac",
                )
                assert reused.workspace_id == "opaque-trusted-7f3c"

        async with session_factory() as session:
            with pytest.raises(WorkspaceOrganizationConflict):
                async with session.begin():
                    await get_or_create_bound_workspace(
                        session,
                        "opaque-trusted-7f3c",
                        "org-other",
                        session_verifier="oidc",
                    )

        assert await _read_binding(binding_database_url, "opaque-trusted-7f3c") == "org-acme"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_trusted_claims_have_one_binding_winner(
    binding_database_url,
) -> None:
    """Concurrent organizations cannot both claim the same opaque workspace."""

    engine = create_async_engine(binding_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = "opaque-race-8a4d"

    async def attempt(organization_id: str):
        """Attempt one transactional binding and return either row or conflict."""

        try:
            async with session_factory() as session:
                async with session.begin():
                    return await get_or_create_bound_workspace(
                        session,
                        workspace_id,
                        organization_id,
                        session_verifier="oidc",
                    )
        except WorkspaceOrganizationConflict as exc:
            return exc

    try:
        results = await asyncio.gather(attempt("org-red"), attempt("org-blue"))
        conflicts = [
            result for result in results if isinstance(result, WorkspaceOrganizationConflict)
        ]
        winners = [result for result in results if not isinstance(result, Exception)]

        assert len(conflicts) == 1
        assert len(winners) == 1
        persisted = await _read_binding(binding_database_url, workspace_id)
        assert persisted in {"org-red", "org-blue"}
        assert winners[0].workspace_id == workspace_id
    finally:
        await engine.dispose()
