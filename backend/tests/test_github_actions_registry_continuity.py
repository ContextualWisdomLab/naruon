"""Cross-observation regressions for GitHub Actions workflow identity continuity."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.github_actions_registry_audit import (
    AuditError,
    TreeSnapshot,
    WorkflowPage,
    WorkflowRecord,
    audit_workflow_registry,
)

OBSERVED_AT = datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc)
BASE_SHA = "a" * 40


class SnapshotClient:
    """Expose one complete branch-stable registry snapshot."""

    def __init__(self, record: WorkflowRecord, tree_paths: set[str]) -> None:
        self.record = record
        self.tree_paths = tree_paths

    def get_default_branch(self, repository: str) -> str:
        """Return the expected protected default branch."""
        assert repository == "ContextualWisdomLab/naruon"
        return "develop"

    def get_branch_sha(self, repository: str, branch: str) -> str:
        """Return an unchanged exact branch SHA."""
        assert repository == "ContextualWisdomLab/naruon"
        assert branch == "develop"
        return BASE_SHA

    def get_tree_snapshot(self, repository: str, commit_sha: str) -> TreeSnapshot:
        """Return exact tree membership for the snapshot."""
        assert repository == "ContextualWisdomLab/naruon"
        assert commit_sha == BASE_SHA
        return TreeSnapshot(paths=frozenset(self.tree_paths), truncated=False)

    def list_workflows_page(
        self,
        repository: str,
        *,
        page: int,
        per_page: int,
    ) -> WorkflowPage:
        """Return one complete workflow page."""
        assert repository == "ContextualWisdomLab/naruon"
        assert page == 1
        assert per_page == 100
        return WorkflowPage(total_count=1, workflows=(self.record,))


def make_record(*, path: str, name: str, state: str = "active") -> WorkflowRecord:
    """Build one stable workflow identity fixture."""
    return WorkflowRecord(workflow_id=9001, name=name, path=path, state=state)


def test_reused_workflow_id_with_new_path_fails_closed() -> None:
    """A stable workflow ID cannot silently authorize a different repository path."""
    old_path = ".github/workflows/old-one-shot.yml"
    new_path = ".github/workflows/new-supported.yml"
    previous = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        SnapshotClient(make_record(path=old_path, name="Old one-shot"), {old_path}),
        observed_at=OBSERVED_AT,
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon",
            SnapshotClient(make_record(path=new_path, name="Supported"), {new_path}),
            observed_at=OBSERVED_AT,
            previous_receipt=previous,
        )

    assert exc_info.value.reason_code == "workflow_id_path_changed"


def test_name_and_state_change_on_same_path_do_not_create_path_authority() -> None:
    """Names and states may change while exact workflow path identity remains stable."""
    path = ".github/workflows/app-ci.yml"
    previous = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        SnapshotClient(make_record(path=path, name="Application CI"), {path}),
        observed_at=OBSERVED_AT,
    )

    current = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        SnapshotClient(
            make_record(path=path, name="Application CI renamed", state="disabled_manually"),
            {path},
        ),
        observed_at=OBSERVED_AT,
        previous_receipt=previous,
    )

    assert current.records[0].workflow_id == previous.records[0].workflow_id
    assert current.records[0].path == path
    assert current.records[0].name == "Application CI renamed"
    assert current.records[0].state == "disabled_manually"


def test_previous_receipt_for_other_repository_is_rejected() -> None:
    """Continuity evidence must belong to the repository being audited."""
    path = ".github/workflows/app-ci.yml"
    previous = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        SnapshotClient(make_record(path=path, name="Application CI"), {path}),
        observed_at=OBSERVED_AT,
    )
    forged_previous = previous.__class__(
        repository="ContextualWisdomLab/other",
        default_branch=previous.default_branch,
        default_branch_sha=previous.default_branch_sha,
        observed_at=previous.observed_at,
        registry_total_count=previous.registry_total_count,
        observed_workflow_count=previous.observed_workflow_count,
        pages=previous.pages,
        records=previous.records,
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon",
            SnapshotClient(make_record(path=path, name="Application CI"), {path}),
            observed_at=OBSERVED_AT,
            previous_receipt=forged_previous,
        )

    assert exc_info.value.reason_code == "previous_receipt_repository_mismatch"
