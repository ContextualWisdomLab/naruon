"""Contract tests for PR-governance concurrency semantics."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-governance.yml"


def test_pr_governance_concurrency_expression_matches_workflow_contract() -> None:
    """Pin push cancellation and serialized cross-event gate publication."""
    workflow_config = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

    assert workflow_config["concurrency"] == {
        "group": (
            "${{ github.workflow }}-"
            "${{ github.event.pull_request.number || "
            "github.event.workflow_run.pull_requests[0].number || "
            "github.event.check_run.pull_requests[0].number || "
            "github.event.inputs.pr_number || github.run_id }}-"
            "${{ github.event_name == 'pull_request_target' && "
            "github.event.action == 'synchronize' && 'synchronize' || 'other' }}"
        ),
        "cancel-in-progress": (
            "${{ github.event_name == 'pull_request_target' && "
            "github.event.action == 'synchronize' }}"
        ),
    }
    assert workflow_config["jobs"]["governance"]["concurrency"] == {
        "group": (
            "${{ github.workflow }}-"
            "${{ github.event.pull_request.number || "
            "github.event.workflow_run.pull_requests[0].number || "
            "github.event.check_run.pull_requests[0].number || "
            "github.event.inputs.pr_number || github.run_id }}-publisher"
        ),
        "cancel-in-progress": False,
    }


def test_pr_governance_concurrency_semantics_cancel_only_superseded_pushes() -> None:
    """Model cancellation plus one serialized evaluator/publisher per PR."""

    def workflow_group(pr_number: int, event_name: str, action: str = "") -> str:
        suffix = (
            "synchronize"
            if event_name == "pull_request_target" and action == "synchronize"
            else "other"
        )
        return f"pr-governance-{pr_number}-{suffix}"

    def publisher_group(pr_number: int) -> str:
        return f"pr-governance-{pr_number}-publisher"

    def expected_cancel(event_name: str, action: str = "") -> bool:
        return event_name == "pull_request_target" and action == "synchronize"

    assert workflow_group(42, "pull_request_target", "synchronize") != workflow_group(
        42, "pull_request_review", "submitted"
    )
    assert workflow_group(42, "pull_request_review", "submitted") == workflow_group(
        42, "workflow_run"
    )
    assert workflow_group(42, "check_run") == workflow_group(42, "workflow_dispatch")
    assert workflow_group(
        42, "pull_request_target", "synchronize"
    ) != workflow_group(43, "pull_request_target", "synchronize")

    # The workflow-level groups deliberately differ so a new push cannot cancel
    # review/recovery work. The governance job itself must still share one PR-
    # scoped concurrency group across every event, otherwise two live metadata
    # snapshots can publish to the same comment/check identity concurrently.
    assert publisher_group(42) == publisher_group(42)
    assert publisher_group(42) != publisher_group(43)

    assert expected_cancel("pull_request_target", "synchronize") is True
    assert expected_cancel("pull_request_review", "submitted") is False
    assert expected_cancel("workflow_run") is False
    assert expected_cancel("check_run") is False
    assert expected_cancel("workflow_dispatch") is False
