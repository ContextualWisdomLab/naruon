from __future__ import annotations

from pathlib import Path
import stat
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "prepare_local_env.py"
PRESERVED_KEYS = (
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "AUTH_SESSION_HMAC_SECRET",
    "ENCRYPTION_KEY",
)


def _run(path: Path, example: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--path",
            str(path),
            "--example",
            str(example),
        ],
        check=True,
        cwd=REPO_ROOT,
    )


def _values(path: Path) -> dict[str, str]:
    return {
        key: value
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
        for key, value in [line.split("=", 1)]
    }


def test_prepare_local_env_is_idempotent_for_generated_secrets(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    path = tmp_path / ".env"
    example.write_text("UNRELATED_SETTING=kept\n", encoding="utf-8")

    _run(path, example)
    first = _values(path)
    _run(path, example)
    second = _values(path)

    for key in PRESERVED_KEYS:
        assert first[key]
        assert second[key] == first[key]
    assert second["UNRELATED_SETTING"] == "kept"
    assert second["POSTGRES_PASSWORD"] in second["DATABASE_URL"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_prepare_local_env_preserves_existing_operator_values(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    path = tmp_path / ".env"
    example.write_text("TEMPLATE_ONLY=value\n", encoding="utf-8")
    path.write_text(
        "\n".join(
            [
                "POSTGRES_DB=workspace_db",
                "POSTGRES_USER=workspace_user",
                "POSTGRES_PASSWORD=keep-this-password",
                "DATABASE_URL=postgresql+asyncpg://existing/db",
                "AUTH_SESSION_HMAC_SECRET=keep-this-session-secret",
                "ENCRYPTION_KEY=keep-this-encryption-key",
                "UNRELATED_SETTING=keep-me",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _run(path, example)
    values = _values(path)

    assert values["POSTGRES_DB"] == "workspace_db"
    assert values["POSTGRES_USER"] == "workspace_user"
    assert values["POSTGRES_PASSWORD"] == "keep-this-password"
    assert values["DATABASE_URL"] == "postgresql+asyncpg://existing/db"
    assert values["AUTH_SESSION_HMAC_SECRET"] == "keep-this-session-secret"
    assert values["ENCRYPTION_KEY"] == "keep-this-encryption-key"
    assert values["UNRELATED_SETTING"] == "keep-me"
    assert "TEMPLATE_ONLY" not in values


def test_prepare_local_env_preserves_literal_quoted_secret_assignments(
    tmp_path: Path,
) -> None:
    example = tmp_path / ".env.example"
    path = tmp_path / ".env"
    example.write_text("TEMPLATE_ONLY=value\n", encoding="utf-8")
    path.write_text(
        "\n".join(
            [
                "POSTGRES_DB=workspace_db",
                "POSTGRES_USER=workspace_user",
                "POSTGRES_PASSWORD='pa$$word$literal'",
                "DATABASE_URL='postgresql+asyncpg://workspace_user:pa%24%24word%24literal@127.0.0.1:15432/workspace_db'",
                "AUTH_SESSION_HMAC_SECRET='session$literal'",
                "ENCRYPTION_KEY='encryption$literal'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    original_assignments = {
        line.split("=", 1)[0]: line
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    }

    _run(path, example)
    resulting_assignments = {
        line.split("=", 1)[0]: line
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    }

    for key in PRESERVED_KEYS:
        assert resulting_assignments[key] == original_assignments[key]


def test_prepare_local_env_replaces_comment_only_managed_values(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    path = tmp_path / ".env"
    example.write_text("TEMPLATE_ONLY=value\n", encoding="utf-8")
    path.write_text(
        "\n".join(
            [
                "POSTGRES_DB=workspace_db",
                "POSTGRES_USER=workspace_user",
                "POSTGRES_PASSWORD= # required",
                "DATABASE_URL='' # required",
                'AUTH_SESSION_HMAC_SECRET="" # required',
                "ENCRYPTION_KEY= # required",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _run(path, example)
    values = _values(path)

    for key in PRESERVED_KEYS:
        assert values[key]
        assert "# required" not in values[key]
    assert values["POSTGRES_PASSWORD"] in values["DATABASE_URL"]
