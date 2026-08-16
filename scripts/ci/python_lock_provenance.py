#!/usr/bin/env python3
"""Validate deterministic offline provenance for hash-pinned Python locks.

This utility deliberately validates only repository-controlled declarations:
exact pins, SHA-256 entries, generator-command binding, and source-lock version
agreement. It does not contact package indexes and therefore does not claim
artifact availability or registry provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = "naruon.python-lock-provenance.v1"
_EXACT_PIN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9._,-]+\])?)"
    r"==(?P<version>[^\s\\;]+)(?:\s*;\s*[^\\]+)?\s*\\?$"
)
_SHA256 = re.compile(r"^--hash=sha256:(?P<digest>[0-9a-fA-F]{64})\s*\\?$")
_SHA256_PREFIX = "--hash=sha256:"
_MANUAL_PIN = re.compile(
    r"(?<![A-Za-z0-9._-])(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"==(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)"
)
_TEXT_PATH = re.compile(r"(?<!\S)(?P<path>[A-Za-z0-9_./-]+\.txt)(?=\s|$)")


def _normalized_name(name: str) -> str:
    """Return the canonical comparison form for one Python project name."""
    return re.sub(r"[-_.]+", "-", name.split("[", 1)[0].lower())


def _relative_path(path: Path, repository_root: Path) -> str:
    """Return a stable POSIX path without leaking an absolute runner location."""
    try:
        relative = path.resolve().relative_to(repository_root.resolve())
    except ValueError:
        return path.name
    return relative.as_posix()


def _violation(code: str, path: str, detail: str) -> dict[str, str]:
    """Create one stable machine-readable validation finding."""
    return {"code": code, "path": path, "detail": detail}


def _header_command(header_lines: list[str], marker: str) -> str | None:
    """Return the first comment command containing ``marker``, if present."""
    for line in header_lines:
        cleaned = line.lstrip("#").strip()
        if marker in cleaned:
            return cleaned
    return None


def _parse_source_pins(text: str) -> dict[str, str]:
    """Return exact direct pins declared by a source requirements file."""
    pins: dict[str, str] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(("#", "-")):
            continue
        match = _EXACT_PIN.fullmatch(stripped)
        if match is not None:
            pins[_normalized_name(match.group("name"))] = match.group("version")
    return pins


def _parse_lock(
    text: str, path: str
) -> tuple[list[str], dict[str, str], int, list[dict[str, str]]]:
    """Parse exact pins and SHA-256 evidence from one requirements lock."""
    header_lines: list[str] = []
    pins: dict[str, str] = {}
    hash_count = 0
    violations: list[dict[str, str]] = []
    current_label: str | None = None
    current_hashes = 0
    seen_requirement = False

    def finalize() -> None:
        nonlocal current_label, current_hashes
        if current_label is not None and current_hashes == 0:
            violations.append(
                _violation(
                    "missing-sha256",
                    path,
                    f"{current_label} has no SHA-256 hash entry",
                )
            )
        current_label = None
        current_hashes = 0

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if not seen_requirement:
                header_lines.append(stripped)
            continue
        if stripped.startswith("--hash="):
            if current_label is None:
                violations.append(
                    _violation(
                        "orphan-hash",
                        path,
                        "hash entry is not attached to a requirement",
                    )
                )
                continue
            sha_match = _SHA256.fullmatch(stripped)
            if sha_match is None:
                if stripped.startswith(_SHA256_PREFIX):
                    violations.append(
                        _violation(
                            "malformed-sha256",
                            path,
                            f"{current_label} has a malformed SHA-256 digest",
                        )
                    )
                continue
            current_hashes += 1
            hash_count += 1
            continue
        if stripped.startswith("-"):
            continue

        finalize()
        seen_requirement = True
        match = _EXACT_PIN.fullmatch(stripped)
        if match is None:
            current_label = stripped.rstrip("\\").strip()
            violations.append(
                _violation(
                    "requirement-not-exactly-pinned",
                    path,
                    f"{current_label} is not an exact == pin",
                )
            )
            continue

        current_label = f"{match.group('name')}=={match.group('version')}"
        normalized_name = _normalized_name(match.group("name"))
        if normalized_name in pins:
            violations.append(
                _violation(
                    "duplicate-requirement",
                    path,
                    f"{current_label} duplicates project {normalized_name}",
                )
            )
        pins[normalized_name] = match.group("version")

    finalize()
    return header_lines, pins, hash_count, violations


def _validate_generation(
    *,
    repository_root: Path,
    header_lines: list[str],
    pins: dict[str, str],
    relative_path: str,
) -> tuple[str, list[dict[str, str]]]:
    """Validate recognized lock-generation declarations without network access."""
    violations: list[dict[str, str]] = []
    uv_command = _header_command(header_lines, "uv pip compile")
    if uv_command is not None:
        output_match = re.search(r"--output-file(?:=|\s+)(?P<path>\S+)", uv_command)
        if output_match is None:
            violations.append(
                _violation(
                    "generation-output-missing",
                    relative_path,
                    "uv generation command does not name --output-file",
                )
            )
        elif Path(output_match.group("path")).as_posix() != relative_path:
            violations.append(
                _violation(
                    "generation-output-mismatch",
                    relative_path,
                    "uv generation output does not match the validated lock path",
                )
            )

        text_paths = [match.group("path") for match in _TEXT_PATH.finditer(uv_command)]
        output_path = output_match.group("path") if output_match is not None else None
        source_paths = [candidate for candidate in text_paths if candidate != output_path]
        if not source_paths:
            violations.append(
                _violation(
                    "generation-input-missing",
                    relative_path,
                    "uv generation command does not name a source requirements file",
                )
            )
            return "uv", violations

        source_path = repository_root / source_paths[-1]
        if not source_path.is_file():
            violations.append(
                _violation(
                    "generation-input-missing",
                    relative_path,
                    f"declared source {source_paths[-1]} is missing",
                )
            )
            return "uv", violations

        source_pins = _parse_source_pins(source_path.read_text(encoding="utf-8"))
        for name, version in sorted(source_pins.items()):
            locked_version = pins.get(name)
            if locked_version != version:
                locked_description = locked_version or "missing"
                violations.append(
                    _violation(
                        "generation-version-mismatch",
                        relative_path,
                        (
                            f"source pin {name}=={version} is locked as "
                            f"{locked_description}"
                        ),
                    )
                )
        return "uv", violations

    pip_command = _header_command(header_lines, "pip download")
    if pip_command is not None:
        command_pins = {
            _normalized_name(match.group("name")): match.group("version")
            for match in _MANUAL_PIN.finditer(pip_command)
        }
        if not command_pins:
            violations.append(
                _violation(
                    "generation-input-missing",
                    relative_path,
                    "pip download generation command does not name an exact package pin",
                )
            )
            return "pip-download", violations
        for name, version in sorted(command_pins.items()):
            locked_version = pins.get(name)
            if locked_version != version:
                locked_description = locked_version or "missing"
                violations.append(
                    _violation(
                        "generation-version-mismatch",
                        relative_path,
                        (
                            f"generator pin {name}=={version} is locked as "
                            f"{locked_description}"
                        ),
                    )
                )
        return "pip-download", violations

    return "manual", violations


def validate_lock_file(lock_path: Path, repository_root: Path) -> dict[str, object]:
    """Validate one lock file and return a deterministic offline receipt."""
    text = lock_path.read_text(encoding="utf-8")
    relative_path = _relative_path(lock_path, repository_root)
    header_lines, pins, hash_count, violations = _parse_lock(text, relative_path)
    generation_mode, generation_violations = _validate_generation(
        repository_root=repository_root,
        header_lines=header_lines,
        pins=pins,
        relative_path=relative_path,
    )
    violations.extend(generation_violations)
    violations.sort(key=lambda item: (item["code"], item["path"], item["detail"]))
    return {
        "path": relative_path,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "status": "failed" if violations else "passed",
        "generation_mode": generation_mode,
        "requirement_count": len(pins),
        "sha256_hash_count": hash_count,
        "violations": violations,
    }


def discover_hash_locks(repository_root: Path) -> list[Path]:
    """Discover active or conventionally named hash-lock requirements files."""
    candidates: list[Path] = []
    for path in repository_root.rglob("requirements*.txt"):
        if any(part in {".git", ".venv", "node_modules"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _SHA256_PREFIX in text or "hash" in path.stem.lower():
            candidates.append(path)
    return sorted(candidates, key=lambda path: _relative_path(path, repository_root))


def validate_repository(repository_root: Path) -> dict[str, object]:
    """Validate every active Python hash lock and aggregate one repository receipt."""
    lock_receipts = [
        validate_lock_file(path, repository_root)
        for path in discover_hash_locks(repository_root)
    ]
    violations = [
        violation
        for receipt in lock_receipts
        for violation in receipt["violations"]
        if isinstance(violation, dict)
    ]
    violations.sort(key=lambda item: (item["code"], item["path"], item["detail"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed" if violations else "passed",
        "lock_files": lock_receipts,
        "violations": violations,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for repository validation."""
    parser = argparse.ArgumentParser(
        description="Validate offline provenance declarations for Python hash locks."
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to validate (default: current working directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the deterministic JSON receipt to stdout.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Run repository validation and return zero only for a passing receipt."""
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    receipt = validate_repository(args.repository_root)
    if args.json:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    else:
        print(f"Python lock provenance: {receipt['status']}")
        for violation in receipt["violations"]:
            print(
                f"{violation['code']}: {violation['path']}: {violation['detail']}"
            )
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
