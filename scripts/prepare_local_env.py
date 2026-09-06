#!/usr/bin/env python3
"""Prepare an idempotent local Compose environment for Naruon.

The helper creates a project-local ``.env`` from ``.env.example`` when needed,
generates only missing secrets, and preserves every existing non-empty managed
assignment verbatim. It never prints secret material.
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import re
import secrets
import stat
from urllib.parse import quote


_MANAGED_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "AUTH_SESSION_HMAC_SECRET",
    "ENCRYPTION_KEY",
)


def _quoted_dotenv_value(value: str) -> str | None:
    """Return a closed quoted Compose dotenv value, or ``None`` when empty."""

    quote_character = value[0]
    escaped = False
    for character_index, character in enumerate(value[1:], start=1):
        if character == "\\" and not escaped:
            escaped = True
            continue
        if character == quote_character and not escaped:
            trailing_text = value[character_index + 1 :].strip()
            if trailing_text and not trailing_text.startswith("#"):
                return value
            quoted_value = value[1:character_index]
            return quoted_value or None
        escaped = False
    return value


def _effective_value(raw_value: str) -> str | None:
    """Return one assignment's effective Compose dotenv value."""

    value = raw_value.strip()
    if not value:
        return None
    if value[0] in {"'", '"'}:
        return _quoted_dotenv_value(value)
    value = re.split(r"\s+#", raw_value, maxsplit=1)[0].strip()
    return value or None


def _assignment_matches(text: str, key: str) -> list[re.Match[str]]:
    """Return ordered assignments for ``key`` so the last one remains effective."""

    return list(re.finditer(rf"(?m)^{re.escape(key)}=(.*)$", text))


def _existing_value(text: str, key: str) -> str | None:
    """Return the effective non-empty Compose dotenv value for ``key``."""

    matches = _assignment_matches(text, key)
    if not matches:
        return None
    return _effective_value(matches[-1].group(1))


def _upsert(text: str, key: str, value: str) -> str:
    """Replace only the effective empty assignment or append a missing key."""

    replacement = f"{key}={value}"
    matches = _assignment_matches(text, key)
    if matches:
        match = matches[-1]
        return f"{text[: match.start()]}{replacement}{text[match.end() :]}"
    separator = "" if not text or text.endswith("\n") else "\n"
    return f"{text}{separator}{replacement}\n"


def _write_private(path: Path, text: str) -> None:
    """Restrict ``path`` before any generated secret material is written."""

    private_mode = stat.S_IRUSR | stat.S_IWUSR
    file_descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
        private_mode,
    )
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as dotenv_file:
        os.fchmod(dotenv_file.fileno(), private_mode)
        os.ftruncate(dotenv_file.fileno(), 0)
        dotenv_file.write(text)


def prepare_local_env(path: Path, example_path: Path) -> None:
    """Create or update ``path`` without reserializing non-empty assignments."""

    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = example_path.read_text(encoding="utf-8")

    existing_values = {key: _existing_value(text, key) for key in _MANAGED_KEYS}
    postgres_db = existing_values["POSTGRES_DB"] or "ai_email"
    postgres_user = existing_values["POSTGRES_USER"] or "postgres"
    postgres_password = existing_values["POSTGRES_PASSWORD"] or secrets.token_urlsafe(32)
    database_url = existing_values["DATABASE_URL"] or (
        "postgresql+asyncpg://"
        f"{quote(postgres_user, safe='')}:{quote(postgres_password, safe='')}"
        f"@127.0.0.1:15432/{quote(postgres_db, safe='')}"
    )
    auth_secret = existing_values["AUTH_SESSION_HMAC_SECRET"] or secrets.token_urlsafe(48)
    encryption_key = existing_values["ENCRYPTION_KEY"] or base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode("ascii")

    values = {
        "POSTGRES_DB": postgres_db,
        "POSTGRES_USER": postgres_user,
        "POSTGRES_PASSWORD": postgres_password,
        "DATABASE_URL": database_url,
        "AUTH_SESSION_HMAC_SECRET": auth_secret,
        "ENCRYPTION_KEY": encryption_key,
    }
    if tuple(values) != _MANAGED_KEYS:
        raise RuntimeError("managed dotenv key order drifted")

    for key, value in values.items():
        if existing_values[key] is not None:
            continue
        text = _upsert(text, key, value)

    _write_private(path, text.rstrip() + "\n")


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=Path(".env"), help="dotenv file to create/update")
    parser.add_argument(
        "--example",
        type=Path,
        default=Path(".env.example"),
        help="template used only when --path does not yet exist",
    )
    return parser


def _project_local_path(path: Path, project_root: Path) -> Path:
    """Return a non-symlink path contained by the project root."""

    candidate = path if path.is_absolute() else project_root / path
    resolved_parent = candidate.parent.resolve()
    try:
        resolved_parent.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"path must stay inside project root: {path}") from exc
    if candidate.is_symlink():
        raise ValueError(f"symbolic links are not allowed: {path}")
    return resolved_parent / candidate.name


def main() -> int:
    """Run the local environment preparation command."""

    parser = _parser()
    args = parser.parse_args()
    try:
        project_root = Path.cwd().resolve()
        path = _project_local_path(args.path, project_root)
        example = _project_local_path(args.example, project_root)
        prepare_local_env(path, example)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
