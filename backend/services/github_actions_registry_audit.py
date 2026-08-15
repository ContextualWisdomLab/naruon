"""Fail-closed classification for GitHub Actions workflow-registry evidence.

The audit is deliberately read-only. A caller supplies a control-plane adapter
implementing :class:`GitHubActionsAuditClient`; this module binds observations
to one immutable default-branch tree and produces evidence that an authorized
operator may review before any separate workflow-disable action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

WORKFLOW_DIRECTORY = ".github/workflows/"
WORKFLOW_PAGE_SIZE = 100

WorkflowClassification = Literal[
    "present_repository_workflow",
    "active_orphan_repository_workflow",
    "disabled_orphan_repository_workflow",
    "dynamic_or_external_workflow",
    "unresolved_workflow_record",
]


class AuditError(RuntimeError):
    """Represent a fail-closed workflow-registry audit outcome.

    Args:
        reason_code: Stable machine-readable failure reason.
        http_status: Optional HTTP status supplied by a control-plane adapter.
    """

    def __init__(self, reason_code: str, *, http_status: int | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.http_status = http_status


@dataclass(frozen=True)
class WorkflowRecord:
    """Represent one immutable GitHub Actions registry record."""

    workflow_id: int
    name: str
    path: str
    state: str


@dataclass(frozen=True)
class WorkflowPage:
    """Represent one paginated Actions workflow-registry response."""

    total_count: int
    workflows: tuple[WorkflowRecord, ...]


@dataclass(frozen=True)
class TreeSnapshot:
    """Represent the exact paths visible in one recursive Git tree."""

    paths: frozenset[str]
    truncated: bool


@dataclass(frozen=True)
class PaginationReceipt:
    """Record one fetched registry page for completeness evidence."""

    page_number: int
    item_count: int
    total_count: int


@dataclass(frozen=True)
class AuditedWorkflowRecord:
    """Bind one workflow record to its mutation-safety classification."""

    workflow_id: int
    name: str
    path: str
    state: str
    classification: WorkflowClassification


@dataclass(frozen=True)
class WorkflowRegistryAuditReceipt:
    """Return immutable evidence for one branch-stable registry observation."""

    repository: str
    default_branch: str
    default_branch_sha: str
    observed_at: str
    registry_total_count: int
    observed_workflow_count: int
    pages: tuple[PaginationReceipt, ...]
    records: tuple[AuditedWorkflowRecord, ...]


class GitHubActionsAuditClient(Protocol):
    """Read-only control-plane adapter required by the registry audit."""

    def get_default_branch(self, repository: str) -> str:
        """Return the repository's current default branch."""

    def get_branch_sha(self, repository: str, branch: str) -> str:
        """Return the exact commit SHA for ``branch``."""

    def get_tree_snapshot(self, repository: str, commit_sha: str) -> TreeSnapshot:
        """Return a recursive path snapshot bound to ``commit_sha``."""

    def list_workflows_page(
        self,
        repository: str,
        *,
        page: int,
        per_page: int,
    ) -> WorkflowPage:
        """Return one workflow-registry page."""


def audit_workflow_registry(
    repository: str,
    client: GitHubActionsAuditClient,
    *,
    observed_at: datetime,
) -> WorkflowRegistryAuditReceipt:
    """Collect and classify a complete workflow registry against one exact tree.

    The function never mutates GitHub. It observes the default branch before and
    after collection and fails closed when the branch moves, the Git tree is
    truncated, pagination is incomplete, or workflow identities are ambiguous.

    Args:
        repository: Repository in ``owner/name`` form.
        client: Read-only GitHub control-plane adapter.
        observed_at: Caller-owned observation timestamp with timezone.

    Returns:
        A branch-stable audit receipt suitable for immutable evidence storage.

    Raises:
        AuditError: If evidence cannot prove a complete, unambiguous snapshot.
        ValueError: If ``observed_at`` is timezone-naive.
    """
    if observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    default_branch = client.get_default_branch(repository)
    default_branch_sha = client.get_branch_sha(repository, default_branch)
    tree_snapshot = client.get_tree_snapshot(repository, default_branch_sha)
    if tree_snapshot.truncated:
        raise AuditError("default_branch_tree_truncated")

    workflows, page_receipts, registry_total_count = _collect_workflows(
        repository,
        client,
    )
    audited_records = _classify_records(workflows, tree_snapshot.paths)

    if client.get_branch_sha(repository, default_branch) != default_branch_sha:
        raise AuditError("default_branch_moved")

    return WorkflowRegistryAuditReceipt(
        repository=repository,
        default_branch=default_branch,
        default_branch_sha=default_branch_sha,
        observed_at=observed_at.isoformat(),
        registry_total_count=registry_total_count,
        observed_workflow_count=len(workflows),
        pages=page_receipts,
        records=audited_records,
    )


def _collect_workflows(
    repository: str,
    client: GitHubActionsAuditClient,
) -> tuple[tuple[WorkflowRecord, ...], tuple[PaginationReceipt, ...], int]:
    """Fetch every registry page and reject incomplete or inconsistent evidence."""
    page_number = 1
    expected_total: int | None = None
    workflows: list[WorkflowRecord] = []
    page_receipts: list[PaginationReceipt] = []

    while expected_total is None or len(workflows) < expected_total:
        page = client.list_workflows_page(
            repository,
            page=page_number,
            per_page=WORKFLOW_PAGE_SIZE,
        )
        if expected_total is None:
            expected_total = page.total_count
        elif page.total_count != expected_total:
            raise AuditError("workflow_registry_total_changed")

        page_receipts.append(
            PaginationReceipt(
                page_number=page_number,
                item_count=len(page.workflows),
                total_count=page.total_count,
            )
        )
        if not page.workflows and len(workflows) < expected_total:
            raise AuditError("workflow_registry_pagination_incomplete")

        workflows.extend(page.workflows)
        if len(workflows) > expected_total:
            raise AuditError("workflow_registry_count_exceeded")
        page_number += 1

    assert expected_total is not None

    workflow_ids: set[int] = set()
    for record in workflows:
        if record.workflow_id in workflow_ids:
            raise AuditError("duplicate_workflow_id")
        workflow_ids.add(record.workflow_id)

    return tuple(workflows), tuple(page_receipts), expected_total


def _classify_records(
    workflows: tuple[WorkflowRecord, ...],
    tree_paths: frozenset[str],
) -> tuple[AuditedWorkflowRecord, ...]:
    """Classify records using exact tree membership rather than workflow names."""
    return tuple(
        AuditedWorkflowRecord(
            workflow_id=record.workflow_id,
            name=record.name,
            path=record.path,
            state=record.state,
            classification=_classify_record(record, tree_paths),
        )
        for record in workflows
    )


def _classify_record(
    record: WorkflowRecord,
    tree_paths: frozenset[str],
) -> WorkflowClassification:
    """Return one fail-closed classification for a workflow registry record."""
    path = record.path
    if _looks_like_repository_workflow(path) and not _is_canonical_workflow_path(path):
        return "unresolved_workflow_record"
    if not path.startswith(WORKFLOW_DIRECTORY):
        return "dynamic_or_external_workflow"
    if path in tree_paths:
        return "present_repository_workflow"
    if record.state == "active":
        return "active_orphan_repository_workflow"
    return "disabled_orphan_repository_workflow"


def _looks_like_repository_workflow(path: str) -> bool:
    """Return whether a path resembles the repository workflow namespace."""
    normalized = path.replace("\\", "/").casefold()
    return normalized.startswith(WORKFLOW_DIRECTORY)


def _is_canonical_workflow_path(path: str) -> bool:
    """Require an exact, unencoded, traversal-free repository workflow path."""
    if not path.startswith(WORKFLOW_DIRECTORY):
        return False
    if "%" in path or "\\" in path or "\x00" in path or "//" in path:
        return False
    suffix = path[len(WORKFLOW_DIRECTORY) :]
    if not suffix:
        return False
    segments = suffix.split("/")
    return all(segment not in {"", ".", ".."} for segment in segments)
