"""Shared fail-closed validation for portable relative evidence paths."""

from __future__ import annotations

import re


WINDOWS_INVALID_COMPONENT_CHARACTERS = frozenset('<>:"|?*')
WINDOWS_RESERVED_COMPONENT_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"COM{index}" for index in "¹²³"}
    | {f"LPT{index}" for index in "¹²³"}
)


def portable_relative_path_parts(
    value: str,
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Return forward-slash path parts after cross-platform safety checks."""

    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"{field_name} must be relative")
    if "\\" in value:
        raise ValueError(f"{field_name} must use forward slashes")
    parts = tuple(value.split("/"))
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{field_name} contains an unsafe component")
    for part in parts:
        if part.endswith((" ", ".")):
            raise ValueError(f"{field_name} contains a non-portable component")
        if any(
            character in WINDOWS_INVALID_COMPONENT_CHARACTERS
            for character in part
        ):
            raise ValueError(f"{field_name} contains a non-portable component")
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED_COMPONENT_NAMES:
            raise ValueError(f"{field_name} contains a reserved component")
    return parts
