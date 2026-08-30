"""Adversarial regressions for the read-only GitHub Actions registry audit."""

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


OBSERVED_AT = datetime(2026, 8, 16, 1, 45, tzinfo=timezone.utc)
BASE_SHA = "a" * 40
MOVED_SHA = "b" * 40


class FakeAuditClient:
    """Return deterministic GitHub control-plane snapshots without network I/O."""

    def __init__(
        self,
        *,
        pages: dict[int, WorkflowPage],
        tree_paths: set[str],
        branch_shas: tuple[str, ...] = (BASE_SHA, BASE_SHA),
        tree_truncated: bool = False,
        failure: AuditError | None = None,
    ) -> None:
        self.pages = pages
        self.tree_paths = tree_paths
        self.branch_shas = list(branch_shas)
        self.tree_truncated = tree_truncated
        self.failure = failure
        self.requested_pages: list[int] = []

    def get_default_branch(self, repository: str) -> str:
        """Return the protected default branch or a configured failure."""
        assert repository == "ContextualWisdomLab/naruon"
        if self.failure is not None:
            raise self.failure
        return "develop"

    def get_branch_sha(self, repository: str, branch: str) -> str:
        """Return branch SHAs in observation order."""
        assert repository == "ContextualWisdomLab/naruon"
        assert branch == "develop"
        return self.branch_shas.pop(0)

    def get_tree_snapshot(self, repository: str, commit_sha: str) -> TreeSnapshot:
        """Return repository paths bound to the first observed branch SHA."""
        assert repository == "ContextualWisdomLab/naruon"
        assert commit_sha == BASE_SHA
        return TreeSnapshot(paths=frozenset(self.tree_paths), truncated=self.tree_truncated)

    def list_workflows_page(
        self,
        repository: str,
        *,
        page: int,
        per_page: int,
    ) -> WorkflowPage:
        """Return one workflow registry page and record pagination behavior."""
        assert repository == "ContextualWisdomLab/naruon"
        assert per_page == 100
        self.requested_pages.append(page)
        return self.pages[page]


def workflow(
    workflow_id: int,
    path: str,
    *,
    state: str = "active",
    name: str | None = None,
) -> WorkflowRecord:
    """Build one workflow registry record for a realistic fixture."""
    return WorkflowRecord(
        workflow_id=workflow_id,
        name=name or path.rsplit("/", 1)[-1],
        path=path,
        state=state,
    )


def page(total_count: int, *records: WorkflowRecord) -> WorkflowPage:
    """Build one pagination-aware registry response."""
    return WorkflowPage(total_count=total_count, workflows=tuple(records))


def test_audit_classifies_exact_present_active_and_orphan_records() -> None:
    """Only exact tree membership may distinguish a live workflow from an orphan."""
    current_path = ".github/workflows/app-ci.yml"
    orphan_path = ".github/workflows/one-shot-nanoid-lock-refresh.yml"
    disabled_path = ".github/workflows/finalize-pr1245-selected-source.yml"
    client = FakeAuditClient(
        pages={
            1: page(
                4,
                workflow(10, current_path, name="Application CI"),
                workflow(11, orphan_path),
                workflow(12, disabled_path, state="disabled_manually"),
                workflow(13, "dynamic/codeql/default-setup", name="CodeQL default setup"),
            )
        },
        tree_paths={current_path},
    )

    receipt = audit_workflow_registry(
        "ContextualWisdomLab/naruon",
        client,
        observed_at=OBSERVED_AT,
    )

    by_id = {record.workflow_id: record for record in receipt.records}
    assert by_id[10].classification == "present_repository_workflow"
    assert by_id[11].classification == "active_orphan_repository_workflow"
    assert by_id[12].classification == "disabled_orphan_repository_workflow"
    assert by_id[13].classification == "dynamic_or_external_workflow"
    assert receipt.default_branch == "develop"
    assert receipt.default_branch_sha == BASE_SHA
    assert receipt.observed_at == "2026-08-16T01:45:00+00:00"
    assert receipt.registry_total_count == 4
    assert receipt.observed_workflow_count == 4
    assert [(p.page_number, p.item_count, p.total_count) for p in receipt.pages] == [
        (1, 4, 4)
    ]


def test_empty_registry_is_complete_evidence() -> None:
    """A genuine zero-count page is complete rather than a pagination failure."""
    client = FakeAuditClient(pages={1: page(0)}, tree_paths=set())

    receipt = audit_workflow_registry(
        "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
    )

    assert receipt.registry_total_count == 0
    assert receipt.observed_workflow_count == 0
    assert receipt.records == ()
    assert client.requested_pages == [1]


def test_timezone_naive_observation_time_is_rejected() -> None:
    """Audit receipts need an offset-bearing observation time for durable evidence."""
    client = FakeAuditClient(pages={1: page(0)}, tree_paths=set())

    with pytest.raises(ValueError, match="timezone-aware"):
        audit_workflow_registry(
            "ContextualWisdomLab/naruon",
            client,
            observed_at=datetime(2026, 8, 16, 1, 45),
        )


def test_legitimate_present_finalizer_like_name_is_not_name_matched_as_orphan() -> None:
    """A finalizer-like name remains present when its exact path exists in the tree."""
    path = ".github/workflows/finalizer-supported-maintenance.yml"
    client = FakeAuditClient(
        pages={1: page(1, workflow(20, path, name="Finalizer supported maintenance"))},
        tree_paths={path},
    )

    receipt = audit_workflow_registry(
        "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
    )

    assert receipt.records[0].classification == "present_repository_workflow"


@pytest.mark.parametrize(
    "hostile_path",
    [
        ".GitHub/workflows/app-ci.yml",
        ".github/workflows/%61pp-ci.yml",
        ".github/workflows/../app-ci.yml",
        ".github/workflows\\app-ci.yml",
        ".github/workflows//app-ci.yml",
        ".github/workflows/app-ci.yml\x00",
        ".github/workflows/",
    ],
)
def test_noncanonical_repository_like_paths_fail_to_unresolved(hostile_path: str) -> None:
    """Case, encoding, traversal, separators, and controls must not authorize mutation."""
    client = FakeAuditClient(
        pages={1: page(1, workflow(30, hostile_path))},
        tree_paths={".github/workflows/app-ci.yml"},
    )

    receipt = audit_workflow_registry(
        "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
    )

    assert receipt.records[0].classification == "unresolved_workflow_record"


def test_registry_pagination_collects_every_page_before_classification() -> None:
    """The detector must collect all registry records rather than trusting page one."""
    paths = {f".github/workflows/live-{index}.yml" for index in range(101)}
    records = [workflow(index + 1, path) for index, path in enumerate(sorted(paths))]
    client = FakeAuditClient(
        pages={1: page(101, *records[:100]), 2: page(101, *records[100:])},
        tree_paths=paths,
    )

    receipt = audit_workflow_registry(
        "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
    )

    assert client.requested_pages == [1, 2]
    assert receipt.registry_total_count == 101
    assert receipt.observed_workflow_count == 101
    assert [entry.page_number for entry in receipt.pages] == [1, 2]


def test_partial_pagination_fails_closed() -> None:
    """An empty page before total_count is reached cannot produce clean evidence."""
    client = FakeAuditClient(
        pages={
            1: page(
                101,
                *[
                    workflow(index, f".github/workflows/{index}.yml")
                    for index in range(100)
                ],
            ),
            2: page(101),
        },
        tree_paths=set(),
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == "workflow_registry_pagination_incomplete"


def test_registry_total_change_between_pages_fails_closed() -> None:
    """A moving registry total invalidates pagination evidence."""
    first_page = tuple(
        workflow(index, f".github/workflows/live-{index}.yml") for index in range(100)
    )
    client = FakeAuditClient(
        pages={1: page(101, *first_page), 2: page(102, workflow(101, ".github/workflows/new.yml"))},
        tree_paths={record.path for record in first_page},
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == "workflow_registry_total_changed"


def test_page_with_more_records_than_total_fails_closed() -> None:
    """A registry response cannot claim fewer records than it actually returns."""
    client = FakeAuditClient(
        pages={
            1: page(
                1,
                workflow(70, ".github/workflows/a.yml"),
                workflow(71, ".github/workflows/b.yml"),
            )
        },
        tree_paths={".github/workflows/a.yml", ".github/workflows/b.yml"},
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == "workflow_registry_count_exceeded"


def test_duplicate_workflow_id_fails_closed() -> None:
    """Reused IDs across pages make the registry snapshot ambiguous."""
    first = workflow(40, ".github/workflows/a.yml")
    second = workflow(40, ".github/workflows/b.yml")
    client = FakeAuditClient(
        pages={1: page(2, first, second)},
        tree_paths={first.path, second.path},
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == "duplicate_workflow_id"


def test_truncated_git_tree_fails_closed() -> None:
    """A truncated recursive tree cannot prove that a workflow path is absent."""
    client = FakeAuditClient(
        pages={1: page(1, workflow(50, ".github/workflows/orphan.yml"))},
        tree_paths=set(),
        tree_truncated=True,
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == "default_branch_tree_truncated"


def test_default_branch_movement_invalidates_the_snapshot() -> None:
    """A branch move during collection must abort instead of publishing stale evidence."""
    client = FakeAuditClient(
        pages={1: page(1, workflow(60, ".github/workflows/app-ci.yml"))},
        tree_paths={".github/workflows/app-ci.yml"},
        branch_shas=(BASE_SHA, MOVED_SHA),
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == "default_branch_moved"


@pytest.mark.parametrize(
    ("reason_code", "status_code"),
    [
        ("github_api_permission_denied", 403),
        ("github_api_resource_not_found", 404),
        ("github_api_transient_failure", 503),
    ],
)
def test_control_plane_failures_remain_explicit(reason_code: str, status_code: int) -> None:
    """Permission, disappearance, and transient failures must never become clean evidence."""
    client = FakeAuditClient(
        pages={},
        tree_paths=set(),
        failure=AuditError(reason_code, http_status=status_code),
    )

    with pytest.raises(AuditError) as exc_info:
        audit_workflow_registry(
            "ContextualWisdomLab/naruon", client, observed_at=OBSERVED_AT
        )

    assert exc_info.value.reason_code == reason_code
    assert exc_info.value.http_status == status_code
