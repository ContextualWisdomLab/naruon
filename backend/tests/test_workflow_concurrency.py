"""Regression tests for GitHub Actions concurrency boundaries."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _workflow_text(name: str) -> str:
    path = REPO_ROOT / ".github" / "workflows" / name
    assert path.exists(), f"workflow is missing: {name}"
    return path.read_text(encoding="utf-8")


def test_bandit_cancels_only_superseded_pull_request_runs() -> None:
    """Keep manual and push scans independent while deduplicating PR scans."""
    workflow = _workflow_text("bandit.yml")
    concurrency = workflow.split("concurrency:\n", 1)[1].split("\npermissions:", 1)[0]

    assert (
        "group: bandit-security-scan-${{ github.event.pull_request.number || github.run_id }}"
        in concurrency
    )
    assert (
        "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in concurrency
    )
    assert "github.ref" not in concurrency
    assert "github.repository" not in concurrency
