"""Regression for a new Actions workflow ID appearing between audit receipts."""

from __future__ import annotations

from datetime import datetime, timezone

from services.github_actions_registry_audit import (
    TreeSnapshot,
    WorkflowPage,
    WorkflowRecord,
    audit_workflow_registry,
)

OBSERVED_AT = datetime(2026, 8, 16, 2, 5, tzinfo=timezone.utc)
BASE_SHA = "a" * 40


class OneWorkflowClient:
    """Expose one complete workflow identity on an unchanged branch."""

    def __init__(self, workflow_id: int, path: str) -> None:
        self.record = WorkflowRecord(
            workflow_id=workflow_id,
            name=path.rsplit("/", 1)[-1],
            path=path,
            state="active",
        )

    def get_default_branch(self, repository: str) -> str:
        """Return the expected default branch."""
        assert repository == "ContextualWisdomLab/naruon"
        return "develop"

    def get_branch_sha(self, repository: str, branch: str) -> str:
        """Return an unchanged exact branch SHA."""
        assert repository == "ContextualWisdomLab/naruon"
        assert branch == "develop"
        return BASE_SHA

    def get_tree_snapshot(self, repository: str, commit_sha: str) -> TreeSnapshot:
        """Expose only the workflow path present in this observation."""
        assert repository == "ContextualWisdomLab/naruon"
        assert commit_sha == BASE_SHA
        return TreeSnapshot(paths=frozenset({self.record.path}), truncated=False)

    def list_workflows_page(
        self,
        repository: str,
        *,
        page: int,
        per_page: int,
    ) -> WorkflowPage:
        """Return the complete one-record registry page."""
        assert repository == "ContextualWisdomLab/naruon"
        assert page == 1
        assert per_page == 100
        return WorkflowPage(total_count=1, workflows=(self.record,))


def test_new_workflow_id_is_not_confused_with_prior_path_identity() -> None:
    """A genuinely new ID may use a different path without impersonating the prior ID."""
    previous = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        OneWorkflowClient(9001, ".github/workflows/old.yml"),
        observed_at=OBSERVED_AT,
    )

    current = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        OneWorkflowClient(9002, ".github/workflows/new.yml"),
        observed_at=OBSERVED_AT,
        previous_receipt=previous,
    )

    assert current.records[0].workflow_id == 9002
    assert current.records[0].path == ".github/workflows/new.yml"
