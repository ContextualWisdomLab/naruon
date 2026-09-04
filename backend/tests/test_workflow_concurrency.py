"""Regression tests for GitHub Actions concurrency boundaries."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_workflow(workflow_name: str) -> dict[str, object]:
    path = REPO_ROOT / ".github" / "workflows" / workflow_name
    assert path.exists(), f"workflow is missing: {workflow_name}"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), (
        f"workflow must parse as a mapping: {workflow_name}"
    )
    return parsed


def test_bandit_cancels_only_superseded_pull_request_runs() -> None:
    """Keep manual and push scans independent while deduplicating PR scans."""
    concurrency = _load_workflow("bandit.yml").get("concurrency")

    assert isinstance(concurrency, dict)
    assert concurrency == {
        "group": "bandit-security-scan-${{ github.repository }}-${{ github.event.pull_request.number || github.run_id }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }


def test_expensive_pr_workflows_cancel_only_active_pr_predecessors() -> None:
    """Draft and closed events cancel stale work without starting heavy jobs."""
    for workflow_name, job_names in {
        "app-ci.yml": ("backend", "frontend"),
        "docker-publish.yml": ("pull_request_image_validation",),
    }.items():
        workflow = _load_workflow(workflow_name)
        pull_request = workflow[True]["pull_request"]
        assert pull_request["types"] == [
            "opened",
            "synchronize",
            "reopened",
            "ready_for_review",
            "converted_to_draft",
            "closed",
        ]
        assert workflow["concurrency"] == {
            "group": "${{ github.workflow }}-${{ github.repository }}-${{ github.event.pull_request.number || github.run_id }}",
            "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
        }
        jobs = workflow["jobs"]
        for job_name in job_names:
            condition = jobs[job_name]["if"]
            assert "!github.event.pull_request.draft" in condition
            assert "github.event.action != 'closed'" in condition
