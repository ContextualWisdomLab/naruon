"""Regression tests for GitHub Actions concurrency boundaries."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _workflow(name: str) -> dict[str, object]:
    path = REPO_ROOT / ".github" / "workflows" / name
    assert path.exists(), f"workflow is missing: {name}"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"workflow must parse as a mapping: {name}"
    return parsed


def test_bandit_cancels_only_superseded_pull_request_runs() -> None:
    """Keep manual and push scans independent while deduplicating PR scans."""
    concurrency = _workflow("bandit.yml").get("concurrency")

    assert isinstance(concurrency, dict)
    assert concurrency == {
        "group": "bandit-security-scan-${{ github.repository }}-${{ github.event.pull_request.number || github.run_id }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }
