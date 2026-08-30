"""Semantic regression tests that keep Actions from publishing source refs."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
SOURCE_REF_ACTIONS = {
    "ad-m/github-push-action",
    "endbug/add-and-commit",
    "peter-evans/create-pull-request",
    "stefanzweifel/git-auto-commit-action",
}


def _effective_contents_permission(
    workflow: dict[str, Any], job: dict[str, Any]
) -> str:
    """Return the effective GitHub token contents permission for one job."""
    permissions = job.get("permissions", workflow.get("permissions"))
    if permissions == "write-all":
        return "write"
    if permissions == "read-all":
        return "read"
    if not isinstance(permissions, dict):
        return "implicit"
    return str(permissions.get("contents", "none")).lower()


def _step_publishes_source_ref(step: dict[str, Any]) -> bool:
    """Detect commands or actions that create or update repository source refs."""
    run = str(step.get("run", ""))
    run_lower = run.lower()
    if re.search(r"\bgit\s+push\b", run_lower):
        return True

    refs_api = re.search(
        r"(?:api\.github\.com|\bgh\s+api\b).*?/git/refs",
        run_lower,
        re.DOTALL,
    )
    mutating_method = re.search(
        r"(?:-x|--request|--method)\s+(?:post|patch)\b", run_lower
    )
    if refs_api and mutating_method:
        return True

    action = str(step.get("uses", "")).split("@", 1)[0].lower()
    if action in SOURCE_REF_ACTIONS:
        return True

    with_values = step.get("with")
    script = str(with_values.get("script", "")) if isinstance(with_values, dict) else ""
    normalized_script = re.sub(r"\s+", "", script).lower()
    return any(
        token in normalized_script
        for token in (
            ".rest.git.createref(",
            ".rest.git.updateref(",
            "github.git.createref(",
            "github.git.updateref(",
        )
    )


def _source_publishing_jobs(workflow: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield jobs that can publish repository source refs and their permissions."""
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job_name, raw_job in jobs.items():
        if not isinstance(raw_job, dict):
            continue
        permission = _effective_contents_permission(workflow, raw_job)
        steps = raw_job.get("steps", [])
        if not isinstance(steps, list):
            continue
        if any(
            isinstance(step, dict) and _step_publishes_source_ref(step)
            for step in steps
        ):
            yield str(job_name), permission


def _load_workflow(text: str) -> dict[str, Any]:
    """Parse one synthetic workflow and assert its mapping shape."""
    workflow = yaml.safe_load(text)
    assert isinstance(workflow, dict)
    return workflow


def test_repository_workflows_do_not_publish_source_refs() -> None:
    """Reject source-ref publishers while allowing package-only publication."""
    offenders: list[str] = []
    governed_workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(
        WORKFLOW_DIR.glob("*.yaml")
    )

    for workflow_path in governed_workflows:
        workflow = _load_workflow(workflow_path.read_text(encoding="utf-8"))
        for job_name, permission in _source_publishing_jobs(workflow):
            offenders.append(
                f"{workflow_path.relative_to(REPO_ROOT).as_posix()}:{job_name}"
                f" (contents={permission})"
            )

    assert offenders == [], (
        "GitHub workflows must not create or update repository source refs: "
        + ", ".join(offenders)
    )


@pytest.mark.parametrize(
    ("workflow_text", "expected"),
    [
        (
            """permissions: write-all
jobs:
  publish:
    steps:
      - run: curl -X POST https://api.github.com/repos/o/r/git/refs
""",
            [("publish", "write")],
        ),
        (
            """permissions:
  contents: read
jobs:
  publish:
    permissions:
      contents: write
    steps:
      - uses: actions/github-script@0123456789012345678901234567890123456789
        with:
          script: |
            github.rest.git.createRef({
              owner: 'o', repo: 'r', ref: 'refs/heads/x', sha: 'a'
            })
""",
            [("publish", "write")],
        ),
        (
            """permissions:
  contents: write
jobs:
  publish:
    steps:
      - run: git push origin HEAD:refs/heads/generated
""",
            [("publish", "write")],
        ),
        (
            """permissions:
  contents: write
jobs:
  publish:
    steps:
      - run: |
          curl --request PATCH \\
            https://api.github.com/repos/o/r/git/refs/heads/generated
""",
            [("publish", "write")],
        ),
        (
            """permissions:
  contents: read
  packages: write
jobs:
  package:
    steps:
      - uses: docker/build-push-action@0123456789012345678901234567890123456789
        with:
          push: true
""",
            [],
        ),
    ],
)
def test_source_publication_detector_covers_permission_and_operation_forms(
    workflow_text: str,
    expected: list[tuple[str, str]],
) -> None:
    """Prove semantic detection across workflow/job permissions and ref writers."""
    assert list(_source_publishing_jobs(_load_workflow(workflow_text))) == expected
