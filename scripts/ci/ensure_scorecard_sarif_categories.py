#!/usr/bin/env python3
"""Preserve Scorecard SARIF categories required by GitHub code scanning."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, BinaryIO, Iterator, NamedTuple

REQUIRED_SCORECARD_CATEGORIES = ("supply-chain/branch-protection",)
SCORECARD_SARIF_FILENAME = "scorecard-results.sarif"
MAX_SARIF_BYTES = 32 * 1024 * 1024


class ScorecardSarifArtifact(NamedTuple):
    """An opened, validated Scorecard artifact and its original file mode."""

    path: Path
    source: BinaryIO
    mode: int


def run_category(run: dict[str, Any]) -> str | None:
    automation_details = run.get("automationDetails")
    if isinstance(automation_details, dict) and isinstance(
        automation_details.get("id"), str
    ):
        return automation_details["id"]
    return None


def scorecard_tool_from(runs: list[dict[str, Any]]) -> dict[str, Any]:
    for run in runs:
        tool = run.get("tool")
        if not isinstance(tool, dict):
            continue
        driver = tool.get("driver")
        if not isinstance(driver, dict):
            continue
        name = driver.get("name")
        if isinstance(name, str) and name.lower() == "scorecard":
            return deepcopy(tool)
    return {"driver": {"name": "Scorecard", "rules": []}}


def placeholder_run(category: str, tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": deepcopy(tool),
        "automationDetails": {"id": category},
        "results": [],
        "properties": {
            "naruonScorecardCompatibility": (
                "empty run preserves GitHub code-scanning category continuity"
            )
        },
    }


def ensure_categories(sarif: dict[str, Any]) -> bool:
    runs = sarif.get("runs")
    if not isinstance(runs, list):
        raise ValueError("SARIF file does not contain a runs array")

    typed_runs = [run for run in runs if isinstance(run, dict)]
    categories = {category for run in typed_runs if (category := run_category(run))}
    missing_categories = [
        category
        for category in REQUIRED_SCORECARD_CATEGORIES
        if category not in categories
    ]
    if not missing_categories:
        return False

    tool = scorecard_tool_from(typed_runs)
    for category in missing_categories:
        runs.append(placeholder_run(category, tool))
    return True


def write_sarif(artifact: ScorecardSarifArtifact, sarif: dict[str, Any]) -> None:
    """Atomically replace the workspace artifact without following hard links."""
    rendered = (json.dumps(sarif, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=artifact.path.parent,
            prefix=f".{artifact.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(
                temporary.fileno(),
                stat.S_IMODE(artifact.mode) | stat.S_IWUSR,
            )
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, artifact.path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@contextmanager
def scorecard_sarif_path(argument: str) -> Iterator[ScorecardSarifArtifact]:
    """Open and validate the single SARIF artifact allowed in the workspace."""
    workspace = Path.cwd().resolve(strict=True)
    expected = workspace / SCORECARD_SARIF_FILENAME
    candidate = Path(os.path.abspath(argument))
    if candidate != expected:
        raise ValueError("SARIF path must name the workspace Scorecard artifact")

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise OSError("secure no-follow file opening is unavailable")
    flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(expected, flags)
    try:
        opened = os.fstat(descriptor)
        named = os.stat(expected, follow_symlinks=False)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("SARIF path must be a regular file in the workspace")
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError("SARIF path changed while it was being opened")
        if opened.st_nlink != 1:
            raise ValueError("SARIF path must not be a hard link")
        if opened.st_size > MAX_SARIF_BYTES:
            raise ValueError("SARIF file exceeds the size limit")

        with os.fdopen(descriptor, "rb", closefd=True) as source:
            descriptor = -1
            yield ScorecardSarifArtifact(expected, source, opened.st_mode)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: ensure_scorecard_sarif_categories.py <scorecard-results.sarif>",
            file=sys.stderr,
        )
        return 64

    try:
        with scorecard_sarif_path(argv[1]) as artifact:
            payload = artifact.source.read(MAX_SARIF_BYTES + 1)
            if len(payload) > MAX_SARIF_BYTES:
                raise ValueError("SARIF file exceeds the size limit")
            if os.fstat(artifact.source.fileno()).st_nlink != 1:
                raise ValueError("SARIF path became a hard link while being read")
            sarif = json.loads(payload.decode("utf-8"))
            changed = ensure_categories(sarif)
            if changed:
                write_sarif(artifact, sarif)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot normalize Scorecard SARIF: {exc}", file=sys.stderr)
        return 65

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
