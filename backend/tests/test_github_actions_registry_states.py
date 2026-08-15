"""Workflow-state regressions for the read-only Actions registry audit."""

from __future__ import annotations

from datetime import datetime, timezone

from services.github_actions_registry_audit import (
    TreeSnapshot,
    WorkflowPage,
    WorkflowRecord,
    audit_workflow_registry,
)

OBSERVED_AT = datetime(2026, 8, 16, 2, 20, tzinfo=timezone.utc)
BASE_SHA = "a" * 40
PATH = ".github/workflows/app-ci.yml"


class OneWorkflowClient:
    """Expose one branch-stable workflow registry record."""

    def __init__(self, *, state: str, path_present: bool) -> None:
        self.record = WorkflowRecord(
            workflow_id=7001,
            name="Application CI",
            path=PATH,
            state=state,
        )
        self.path_present = path_present

    def get_default_branch(self, repository: str) -> str:
        """Return the protected default branch."""
        assert repository == "ContextualWisdomLab/naruon"
        return "develop"

    def get_branch_sha(self, repository: str, branch: str) -> str:
        """Return an unchanged branch SHA for both observations."""
        assert repository == "ContextualWisdomLab/naruon"
        assert branch == "develop"
        return BASE_SHA

    def get_tree_snapshot(self, repository: str, commit_sha: str) -> TreeSnapshot:
        """Return exact tree membership for the workflow path."""
        assert repository == "ContextualWisdomLab/naruon"
        assert commit_sha == BASE_SHA
        paths = frozenset({PATH}) if self.path_present else frozenset()
        return TreeSnapshot(paths=paths, truncated=False)

    def list_workflows_page(
        self,
        repository: str,
        *,
        page: int,
        per_page: int,
    ) -> WorkflowPage:
        """Return one complete registry page."""
        assert repository == "ContextualWisdomLab/naruon"
        assert page == 1
        assert per_page == 100
        return WorkflowPage(total_count=1, workflows=(self.record,))


def classification(*, state: str, path_present: bool) -> str:
    """Return the classification for one workflow state/path combination."""
    receipt = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        OneWorkflowClient(state=state, path_present=path_present),
        observed_at=OBSERVED_AT,
    )
    return receipt.records[0].classification


def test_documented_disabled_states_are_nonactive_orphans_when_path_is_absent() -> None:
    """Every documented disabled state remains distinguishable from an active orphan."""
    for state in ("disabled_fork", "disabled_inactivity", "disabled_manually"):
        assert classification(state=state, path_present=False) == (
            "disabled_orphan_repository_workflow"
        )


def test_deleted_state_is_historical_when_path_is_absent() -> None:
    """GitHub's deleted state represents a non-active historical workflow identity."""
    assert classification(state="deleted", path_present=False) == (
        "disabled_orphan_repository_workflow"
    )


def test_deleted_state_conflicting_with_present_tree_path_is_unresolved() -> None:
    """A registry/tree contradiction must not be reported as ordinary present evidence."""
    assert classification(state="deleted", path_present=True) == (
        "unresolved_workflow_record"
    )


def test_unknown_state_is_unresolved_when_path_is_absent() -> None:
    """Schema drift must fail closed instead of being treated as disabled evidence."""
    assert classification(state="paused_by_policy", path_present=False) == (
        "unresolved_workflow_record"
    )


def test_unknown_state_is_unresolved_even_when_tree_path_is_present() -> None:
    """Exact tree membership does not make an unknown control-plane state trustworthy."""
    assert classification(state="paused_by_policy", path_present=True) == (
        "unresolved_workflow_record"
    )
