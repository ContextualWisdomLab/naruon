"""Tests for Cloud Agent local-Postgres role password reconciliation.

The start path must reject an empty role secret and must never interpolate
that secret into a ``psql -c`` SQL string or process argv.
"""

from __future__ import annotations

import pytest

from scripts.reconcile_local_postgres_role import (
    build_alter_role_sql,
    database_url_password,
    reconcile_local_postgres_role,
)


def test_database_url_password_rejects_empty_secret() -> None:
    with pytest.raises(ValueError, match="local database configuration is incomplete"):
        database_url_password("DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/ai_email\n")


def test_database_url_password_rejects_missing_url() -> None:
    with pytest.raises(ValueError, match="local database configuration is incomplete"):
        database_url_password("DEBUG=false\n")


def test_database_url_password_unquotes_url_encoded_secret() -> None:
    assert (
        database_url_password(
            "DATABASE_URL=postgresql+asyncpg://postgres:a%27b@127.0.0.1:5432/ai_email\n"
        )
        == "a'b"
    )


def test_build_alter_role_sql_dollar_quotes_metacharacters() -> None:
    secret = "x'; DROP ROLE postgres; --"
    sql = build_alter_role_sql(secret)
    assert "DROP ROLE postgres" in sql
    assert "PASSWORD '" not in sql
    assert sql.startswith("ALTER USER postgres WITH PASSWORD $")
    assert sql.endswith(";\n") or sql.endswith(";")


def test_reconcile_local_postgres_role_keeps_secret_off_argv() -> None:
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["input"] = kwargs.get("input")
        captured["check"] = kwargs.get("check")

        class _Completed:
            returncode = 0

        return _Completed()

    secret = "quote'me;and\\back"
    reconcile_local_postgres_role(secret, runner=fake_run)
    argv = captured["argv"]
    assert isinstance(argv, list)
    assert all(secret not in str(part) for part in argv)
    assert "-c" not in argv
    assert secret in str(captured["input"])
    assert captured["check"] is True
