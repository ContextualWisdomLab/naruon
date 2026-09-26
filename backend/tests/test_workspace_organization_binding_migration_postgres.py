"""PostgreSQL acceptance for auditable workspace-organization binding.

The workspace identifier is an opaque authenticated claim. Historical ownership
must therefore be recovered only from server-side evidence already persisted in
``workspace_documents.organization_id``; identifier shape is not ownership
evidence. Ambiguous and evidence-free workspaces stay unbound so compatibility
access can fail closed instead of guessing a tenant.
"""

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
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings

pytestmark = pytest.mark.postgres

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_PRE_BINDING_REVISION = "0019_email_read_state_repair"


def _run_migrations(database_url: str, revision: str = "head") -> None:
    result = subprocess.run(
        [sys.executable, str(_BACKEND_ROOT / "scripts" / "migrate_db.py"), revision],
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
async def fresh_database_url():
    base_url = make_url(settings.DATABASE_URL)
    database_name = f"test_workspace_binding_{uuid.uuid4().hex[:12]}"

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
        yield database_url
    finally:
        try:
            await admin(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        except Exception as exc:
            pytest.fail(
                f"PostgreSQL cleanup failed for workspace binding acceptance: {exc}",
                pytrace=False,
            )


async def _seed_historical_workspace_evidence(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for workspace_id in (
                "opaque-unambiguous-7f3c",
                "opaque-ambiguous-8a4d",
                "opaque-unbound-9b5e",
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO workspace_entities
                            (workspace_id, workspace_name, workspace_domain, created_at)
                        VALUES (:workspace_id, :workspace_id, NULL, now())
                        """
                    ),
                    {"workspace_id": workspace_id},
                )

            documents = (
                (
                    "doc-unambiguous-known",
                    "opaque-unambiguous-7f3c",
                    "org-acme",
                ),
                (
                    "doc-unambiguous-legacy",
                    "opaque-unambiguous-7f3c",
                    None,
                ),
                ("doc-ambiguous-a", "opaque-ambiguous-8a4d", "org-red"),
                ("doc-ambiguous-b", "opaque-ambiguous-8a4d", "org-blue"),
                ("doc-ambiguous-legacy", "opaque-ambiguous-8a4d", None),
                ("doc-unbound-legacy", "opaque-unbound-9b5e", None),
            )
            for document_id, workspace_id, organization_id in documents:
                await connection.execute(
                    text(
                        """
                        INSERT INTO workspace_documents
                            (document_id, workspace_id, organization_id,
                             document_name, document_type, document_content,
                             document_status, created_at)
                        VALUES
                            (:document_id, :workspace_id, :organization_id,
                             :document_id, 'text/markdown', '# historical',
                             'uploaded', now())
                        """
                    ),
                    {
                        "document_id": document_id,
                        "workspace_id": workspace_id,
                        "organization_id": organization_id,
                    },
                )
    finally:
        await engine.dispose()


async def _read_bindings(database_url: str) -> tuple[dict[str, str | None], dict[str, str | None]]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            workspace_result = await connection.execute(
                text(
                    "SELECT workspace_id, organization_id "
                    "FROM workspace_entities ORDER BY workspace_id"
                )
            )
            document_result = await connection.execute(
                text(
                    "SELECT document_id, organization_id "
                    "FROM workspace_documents ORDER BY document_id"
                )
            )
            return (
                {row.workspace_id: row.organization_id for row in workspace_result},
                {row.document_id: row.organization_id for row in document_result},
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_binding_migration_uses_only_unambiguous_persisted_ownership_evidence(
    fresh_database_url,
) -> None:
    """Bind/backfill one-owner history and leave ambiguous or unknown history closed."""

    _run_migrations(fresh_database_url, revision=_PRE_BINDING_REVISION)
    await _seed_historical_workspace_evidence(fresh_database_url)

    _run_migrations(fresh_database_url)
    workspace_bindings, document_bindings = await _read_bindings(fresh_database_url)

    assert workspace_bindings["opaque-unambiguous-7f3c"] == "org-acme"
    assert document_bindings["doc-unambiguous-legacy"] == "org-acme"

    assert workspace_bindings["opaque-ambiguous-8a4d"] is None
    assert document_bindings["doc-ambiguous-legacy"] is None

    assert workspace_bindings["opaque-unbound-9b5e"] is None
    assert document_bindings["doc-unbound-legacy"] is None

    # A repeated managed upgrade is a required deployment path. It must not
    # invent new ownership or mutate the fail-closed ambiguous/unbound rows.
    _run_migrations(fresh_database_url)
    repeated_workspace_bindings, repeated_document_bindings = await _read_bindings(
        fresh_database_url
    )
    assert repeated_workspace_bindings == workspace_bindings
    assert repeated_document_bindings == document_bindings
