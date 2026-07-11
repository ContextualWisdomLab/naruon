from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

ENV_FILE_PATHS = ("~/.env", "../.env", ".env")


def operator_home() -> Path:
    """Return the operator home directory, preferring explicit HOME overrides."""
    configured_home = os.environ.get("HOME")
    if configured_home:
        return Path(configured_home).expanduser()
    return Path.home()


def expand_operator_path(path: str | os.PathLike[str]) -> Path:
    """Expand leading ``~`` against the operator home directory."""
    path_text = os.fspath(path)
    if path_text == "~":
        return operator_home()
    if path_text.startswith("~/") or path_text.startswith("~\\"):
        return operator_home() / path_text[2:]
    return Path(path_text).expanduser()


def operator_env_file_paths(paths: Iterable[str] = ENV_FILE_PATHS) -> tuple[str, ...]:
    """Return env-file paths with operator-home expansion applied."""
    return tuple(str(expand_operator_path(path)) for path in paths)
