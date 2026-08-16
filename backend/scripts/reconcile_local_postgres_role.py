"""Reconcile the local Cloud Agent Postgres role secret without SQL interpolation.

Cloud Agent ``start.sh`` keeps the ``postgres`` role aligned with the
generated ``DATABASE_URL``. The secret must travel only on ``psql`` stdin as
dollar-quoted SQL so a quote or backslash in an existing ``~/.env`` cannot
break out of ``ALTER USER ... PASSWORD`` and does not appear on the process
command line.
"""

from __future__ import annotations

import argparse
import secrets
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

INCOMPLETE_LOCAL_DATABASE_CONFIG = "local database configuration is incomplete"
_ROLE_NAME = "postgres"


def database_url_password(env_text: str) -> str:
    """Return the ``DATABASE_URL`` user secret, or fail closed when it is absent."""
    for line in env_text.splitlines():
        if line.startswith("DATABASE_URL="):
            raw_url = line.split("=", 1)[1].strip()
            secret = unquote(urlsplit(raw_url).password or "")
            if not secret:
                raise ValueError(INCOMPLETE_LOCAL_DATABASE_CONFIG)
            return secret
    raise ValueError(INCOMPLETE_LOCAL_DATABASE_CONFIG)


def build_alter_role_sql(secret: str, *, role_name: str = _ROLE_NAME) -> str:
    """Build ``ALTER USER`` SQL that dollar-quotes ``secret``.

    The tag is regenerated until it is absent from the secret so the closer
    cannot appear inside the quoted value.
    """
    if not secret:
        raise ValueError(INCOMPLETE_LOCAL_DATABASE_CONFIG)
    tag = f"naruon{secrets.token_hex(16)}"
    while tag in secret:
        tag = f"naruon{secrets.token_hex(16)}"
    return f"ALTER USER {role_name} WITH PASSWORD ${tag}${secret}${tag};\n"


def reconcile_local_postgres_role(
    secret: str,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> None:
    """Apply the role secret through ``psql`` stdin, never ``psql -c``."""
    sql = build_alter_role_sql(secret)
    runner(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        text=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main(argv: list[str] | None = None) -> int:
    """Read an env file and align the local ``postgres`` role secret."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        required=True,
        help="Path to the local env file that already contains DATABASE_URL.",
    )
    args = parser.parse_args(argv)
    env_text = Path(args.env_file).read_text(encoding="utf-8")
    reconcile_local_postgres_role(database_url_password(env_text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
