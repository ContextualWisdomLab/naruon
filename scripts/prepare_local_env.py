#!/usr/bin/env python3
"""Prepare an idempotent local Compose environment for Naruon.

The helper creates a project-local ``.env`` from ``.env.example`` when needed,
generates only missing secrets, and preserves every existing non-empty managed
value. It never prints secret material.
"""

from __future__ import annotations

import argparse
import base64
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


def _existing_value(text: str, key: str) -> str | None:
    """Return a non-empty dotenv value for ``key``, stripping simple quotes."""

    match = re.search(rf"(?m)^{re.escape(key)}=(.*)$", text)
    if match is None:
        return None
    value = match.group(1).strip()
    if not value:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value or None


def _upsert(text: str, key: str, value: str) -> str:
    """Replace or append one dotenv assignment without disturbing other lines."""

    pattern = rf"(?m)^{re.escape(key)}=.*$"
    replacement = f"{key}={value}"
    if re.search(pattern, text):
        return re.sub(pattern, replacement, text)
    separator = "" if not text or text.endswith("\n") else "\n"
    return f"{text}{separator}{replacement}\n"


def prepare_local_env(path: Path, example_path: Path) -> None:
    """Create or update ``path`` while preserving existing non-empty secrets."""

    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = example_path.read_text(encoding="utf-8")

    postgres_db = _existing_value(text, "POSTGRES_DB") or "ai_email"
    postgres_user = _existing_value(text, "POSTGRES_USER") or "postgres"
    postgres_password = _existing_value(text, "POSTGRES_PASSWORD") or secrets.token_urlsafe(32)
    database_url = _existing_value(text, "DATABASE_URL") or (
        "postgresql+asyncpg://"
        f"{quote(postgres_user, safe='')}:{quote(postgres_password, safe='')}"
        f"@127.0.0.1:15432/{quote(postgres_db, safe='')}"
    )
    auth_secret = _existing_value(text, "AUTH_SESSION_HMAC_SECRET") or secrets.token_urlsafe(48)
    encryption_key = _existing_value(text, "ENCRYPTION_KEY") or base64.urlsafe_b64encode(
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
        text = _upsert(text, key, value)

    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


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


def main() -> int:
    """Run the local environment preparation command."""

    args = _parser().parse_args()
    try:
        prepare_local_env(args.path, args.example)
    except OSError as exc:
        _parser().error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
