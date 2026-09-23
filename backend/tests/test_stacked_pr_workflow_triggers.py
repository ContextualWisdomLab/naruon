"""Guard repo-local PR validation on dependent stacked pull requests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
PR_VALIDATION_WORKFLOWS = (
    ".github/workflows/app-ci.yml",
    ".github/workflows/bandit.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/docker-publish.yml",
)
PLAYWRIGHT_UPLOAD_PIN = (
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
)
EXACT_HEAD_REF = "${{ github.event.pull_request.head.sha || github.sha }}"


@pytest.mark.parametrize("workflow_path", PR_VALIDATION_WORKFLOWS)
def test_repo_local_pr_validation_accepts_every_base_branch(workflow_path: str) -> None:
    """Require an unfiltered pull_request trigger for every stacked PR base."""
    workflow_text = (REPO_ROOT / workflow_path).read_text(encoding="utf-8")
    # BaseLoader preserves the Actions `on` key instead of YAML 1.1 boolean coercion.
    workflow_events = yaml.load(workflow_text, Loader=yaml.BaseLoader)["on"]
    assert "pull_request" in workflow_events
    pull_request_config = workflow_events["pull_request"] or {}
    assert "branches" not in pull_request_config
    assert "branches-ignore" not in pull_request_config


@pytest.mark.parametrize(
    "branch_filter",
    [
        "branches: ['**']",
        "branches: ['**', '!feature/**']",
        "branches: [develop] # '**' is only a comment",
        "branches-ignore: [archive/**]",
    ],
)
def test_stacked_trigger_guard_rejects_any_base_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch_filter: str
) -> None:
    """Do not encode all-base verification through mutable branch patterns."""
    workflow_path = tmp_path / "workflow.yml"
    workflow_path.write_text(
        f"on:\n  pull_request:\n    {branch_filter}\n", encoding="utf-8"
    )
    monkeypatch.setitem(globals(), "REPO_ROOT", tmp_path)
    with pytest.raises(AssertionError):
        test_repo_local_pr_validation_accepts_every_base_branch("workflow.yml")


def test_application_ci_executes_and_labels_exact_head_browser_acceptance() -> None:
    """Require Playwright evidence to execute and identify the exact PR head."""
    workflow_path = REPO_ROOT / ".github/workflows/app-ci.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    for job_name in ("backend", "frontend"):
        job_steps = workflow["jobs"][job_name]["steps"]
        steps_by_name = {step.get("name"): step for step in job_steps}
        checkout_step = steps_by_name["Checkout repository"]
        checkout_options = checkout_step.get("with") or {}
        assert checkout_options.get("ref") == EXACT_HEAD_REF

    frontend_steps = workflow["jobs"]["frontend"]["steps"]
    steps_by_name = {step.get("name"): step for step in frontend_steps}

    browser_step = steps_by_name["Run Playwright browser acceptance"]
    browser_command = browser_step["run"]
    assert "pnpm run test:e2e" in browser_command
    browser_env = browser_step.get("env") or {}
    assert "LIVE_BASE_URL" not in browser_env
    assert "RUN_LIVE_E2E" not in browser_env

    evidence_step = steps_by_name["Upload Playwright browser evidence"]
    assert evidence_step["uses"] == PLAYWRIGHT_UPLOAD_PIN
    assert evidence_step["if"] == "${{ always() }}"
    evidence_name = evidence_step["with"]["name"]
    assert EXACT_HEAD_REF in evidence_name
    evidence_paths = evidence_step["with"]["path"]
    assert "frontend/playwright-report/" in evidence_paths
    assert "frontend/test-results/" in evidence_paths
