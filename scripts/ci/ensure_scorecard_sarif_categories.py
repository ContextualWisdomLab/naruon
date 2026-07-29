#!/usr/bin/env python3
"""Preserve Scorecard SARIF categories required by GitHub code scanning."""

from __future__ import annotations

import json
import stat
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REQUIRED_SCORECARD_CATEGORIES = ("supply-chain/branch-protection",)


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


def write_sarif(path: Path, sarif: dict[str, Any]) -> None:
    mode = path.stat().st_mode
    if mode & stat.S_IWUSR == 0:
        path.chmod(mode | stat.S_IWUSR)
    path.write_text(
        json.dumps(sarif, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: ensure_scorecard_sarif_categories.py <scorecard-results.sarif>",
            file=sys.stderr,
        )
        return 64

    sarif_path = Path(argv[1])
    try:
        sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
        changed = ensure_categories(sarif)
        if changed:
            write_sarif(sarif_path, sarif)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot normalize Scorecard SARIF: {exc}", file=sys.stderr)
        return 65

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
