"""Contract tests for PR-governance concurrency semantics."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-governance.yml"


def test_pr_governance_concurrency_expression_matches_workflow_contract() -> None:
    """Pin push cancellation and lossless serialized cross-event publication."""
    workflow_config = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

    assert workflow_config["concurrency"] == {
        "group": (
            "${{ github.workflow }}-"
            "${{ github.event.pull_request.number || "
            "github.event.workflow_run.pull_requests[0].number || "
            "github.event.check_run.pull_requests[0].number || "
            "github.event.inputs.pr_number || github.run_id }}-"
            "${{ github.event_name == 'pull_request_target' && "
            "github.event.action == 'synchronize' && 'synchronize' || github.run_id }}"
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
        "queue": "max",
    }


def test_pr_governance_concurrency_semantics_cancel_only_superseded_pushes() -> None:
    """Model cancellation plus one lossless serialized evaluator/publisher per PR."""

    def workflow_group(
        pr_number: int,
        event_name: str,
        action: str = "",
        run_id: int = 1,
    ) -> str:
        suffix = (
            "synchronize"
            if event_name == "pull_request_target" and action == "synchronize"
            else str(run_id)
        )
        return f"pr-governance-{pr_number}-{suffix}"

    def publisher_group(pr_number: int, event_name: str, action: str = "") -> str:
        del event_name, action
        return f"pr-governance-{pr_number}-publisher"

    def expected_cancel(event_name: str, action: str = "") -> bool:
        return event_name == "pull_request_target" and action == "synchronize"

    assert workflow_group(42, "pull_request_target", "synchronize", 100) == workflow_group(
        42, "pull_request_target", "synchronize", 101
    )
    assert workflow_group(42, "pull_request_review", "submitted", 200) != workflow_group(
        42, "workflow_run", run_id=201
    )
    assert workflow_group(42, "check_run", run_id=202) != workflow_group(
        42, "workflow_dispatch", run_id=203
    )
    assert workflow_group(
        42, "pull_request_target", "synchronize", 100
    ) != workflow_group(43, "pull_request_target", "synchronize", 100)

    # Non-synchronize workflows are unique at workflow level so they cannot
    # cancel one another. Their governance jobs then converge on one PR-scoped
    # publisher group, which queues every evaluation and prevents concurrent
    # writes to the shared marker comment/check identity.
    assert publisher_group(42, "pull_request_target", "synchronize") == publisher_group(
        42, "pull_request_review", "submitted"
    )
    assert publisher_group(42, "workflow_run") == publisher_group(42, "check_run")
    assert publisher_group(42, "check_run") == publisher_group(42, "workflow_dispatch")
    assert publisher_group(42, "workflow_dispatch") != publisher_group(
        43, "workflow_dispatch"
    )

    assert expected_cancel("pull_request_target", "synchronize") is True
    assert expected_cancel("pull_request_review", "submitted") is False
    assert expected_cancel("workflow_run") is False
    assert expected_cancel("check_run") is False
    assert expected_cancel("workflow_dispatch") is False
