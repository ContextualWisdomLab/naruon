"""Source contracts for the repo-managed Cloud Agent environment scripts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = (REPO_ROOT / ".cursor" / "install.sh").read_text(encoding="utf-8")
START_SH = (REPO_ROOT / ".cursor" / "start.sh").read_text(encoding="utf-8")
ENVIRONMENT_JSON = (REPO_ROOT / ".cursor" / "environment.json").read_text(
    encoding="utf-8"
)


def test_install_sh_pins_python_requirements_with_hashes() -> None:
    assert "requirements-hashes.txt" in INSTALL_SH
    assert "--require-hashes" in INSTALL_SH
    assert "pip install -r requirements.txt" not in INSTALL_SH
    assert "pip install --upgrade pip" not in INSTALL_SH


def test_start_sh_does_not_interpolate_role_secret_into_sql() -> None:
    assert "PASSWORD '${DB_PASSWORD}'" not in START_SH
    assert "ALTER USER postgres WITH PASSWORD '" not in START_SH
    assert "reconcile_local_postgres_role.py" in START_SH


def test_start_sh_fails_closed_when_postgres_never_becomes_ready() -> None:
    assert "pg_isready" in START_SH
    assert "did not become ready" in START_SH
    assert "exit 1" in START_SH


def test_environment_json_keeps_servers_in_terminals_not_install() -> None:
    assert "bash .cursor/install.sh" in ENVIRONMENT_JSON
    assert "bash .cursor/start.sh" in ENVIRONMENT_JSON
    assert "scripts/start_backend.py" in ENVIRONMENT_JSON
    assert "corepack pnpm@11.5.3 dev" in ENVIRONMENT_JSON