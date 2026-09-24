"""Real PostgreSQL acceptance for personal opaque-workspace ownership binding."""

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
    get_or_create_personal_workspace,
)

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
async def personal_binding_database_url():
    """Create an isolated database; unavailable PostgreSQL is an acceptance failure."""

    base_url = make_url(settings.DATABASE_URL)
    database_name = f"test_personal_workspace_{uuid.uuid4().hex[:12]}"

    async def admin(sql: str) -> None:
        """Execute one database-administration statement outside the test database."""

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
            f"PostgreSQL is required for personal workspace acceptance: {exc}",
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
                f"PostgreSQL cleanup failed for personal workspace acceptance: {exc}",
                pytrace=False,
            )


async def _read_binding(
    database_url: str,
    workspace_id: str,
) -> tuple[str | None, str | None] | None:
    """Read registry ownership independently of the service transaction."""

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


@pytest.mark.asyncio
async def test_personal_binding_requires_trusted_establishment_and_rejects_other_user(
    personal_binding_database_url,
) -> None:
    """HMAC may consume personal ownership but cannot establish or reassign it."""

    engine = create_async_engine(personal_binding_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            with pytest.raises(WorkspaceOrganizationBindingRequired):
                async with session.begin():
                    await get_or_create_personal_workspace(
                        session,
                        "opaque-personal-hmac-unbound-1",
                        "member-a",
                        session_verifier="hmac",
                    )

        assert (
            await _read_binding(
                personal_binding_database_url,
                "opaque-personal-hmac-unbound-1",
            )
            is None
        )

        async with session_factory() as session:
            async with session.begin():
                created = await get_or_create_personal_workspace(
                    session,
                    "opaque-personal-trusted-7f3c",
                    "member-a",
                    session_verifier="override",
                )
                assert created.workspace_id == "opaque-personal-trusted-7f3c"

        assert await _read_binding(
            personal_binding_database_url,
            "opaque-personal-trusted-7f3c",
        ) == (None, "member-a")

        async with session_factory() as session:
            async with session.begin():
                reused = await get_or_create_personal_workspace(
                    session,
                    "opaque-personal-trusted-7f3c",
                    "member-a",
                    session_verifier="hmac",
                )
                assert reused.workspace_id == "opaque-personal-trusted-7f3c"

        async with session_factory() as session:
            with pytest.raises(WorkspaceOrganizationConflict):
                async with session.begin():
                    await get_or_create_personal_workspace(
                        session,
                        "opaque-personal-trusted-7f3c",
                        "member-b",
                        session_verifier="oidc",
                    )

        assert await _read_binding(
            personal_binding_database_url,
            "opaque-personal-trusted-7f3c",
        ) == (None, "member-a")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_personal_claims_have_one_owner_winner(
    personal_binding_database_url,
) -> None:
    """Concurrent users cannot both claim the same personal opaque workspace."""

    engine = create_async_engine(personal_binding_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = "opaque-personal-race-8a4d"

    async def attempt(owner_user_id: str):
        """Attempt one transactional personal binding and return row or conflict."""

        try:
            async with session_factory() as session:
                async with session.begin():
                    return await get_or_create_personal_workspace(
                        session,
                        workspace_id,
                        owner_user_id,
                        session_verifier="oidc",
                    )
        except WorkspaceOrganizationConflict as exc:
            return exc

    try:
        results = await asyncio.gather(attempt("member-red"), attempt("member-blue"))
        conflicts = [
            result
            for result in results
            if isinstance(result, WorkspaceOrganizationConflict)
        ]
        winners = [result for result in results if not isinstance(result, Exception)]

        assert len(conflicts) == 1
        assert len(winners) == 1
        persisted = await _read_binding(personal_binding_database_url, workspace_id)
        assert persisted in {(None, "member-red"), (None, "member-blue")}
        assert winners[0].workspace_id == workspace_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_personal_binding_cannot_replace_organization_binding(
    personal_binding_database_url,
) -> None:
    """Personal ownership cannot cross the registry's organization-bound invariant."""

    engine = create_async_engine(personal_binding_database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO workspace_entities "
                    "(workspace_id, workspace_name, organization_id, owner_user_id, created_at) "
                    "VALUES (:workspace_id, :workspace_id, :organization_id, NULL, now())"
                ),
                {
                    "workspace_id": "opaque-org-owned-9b5e",
                    "organization_id": "org-acme",
                },
            )

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            with pytest.raises(WorkspaceOrganizationConflict):
                async with session.begin():
                    await get_or_create_personal_workspace(
                        session,
                        "opaque-org-owned-9b5e",
                        "member-a",
                        session_verifier="server",
                    )

        assert await _read_binding(
            personal_binding_database_url,
            "opaque-org-owned-9b5e",
        ) == ("org-acme", None)
    finally:
        await engine.dispose()
