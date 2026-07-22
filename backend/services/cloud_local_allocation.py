"""Strict validation for read-only DiskSage cloud local-allocation evidence."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_U64 = 18_446_744_073_709_551_615
BASE_NOTICES = (
    "metadata-only-content-not-opened",
    "embedded-production-metadata-not-inspected",
    "provider-sync-not-attested",
    "inventory-does-not-authorize-eviction",
)
MAX_PATH_UTF8_BYTES = 65_536

U64 = Annotated[int, Field(ge=0, le=MAX_U64)]
EpochMilliseconds = U64
BoundedText = Annotated[str, Field(min_length=1, max_length=65_536)]
ShortText = Annotated[str, Field(min_length=1, max_length=4_096)]
CloudProvider = Literal["icloud", "onedrive", "google-drive"]
CloudAccountScope = Literal["personal", "organization", "shared", "unknown"]
StopReason = Literal[
    "max-duration-reached",
    "max-entries-reached",
    "max-depth-reached",
    "entry-errors",
    "allocated-byte-evidence-unavailable",
    "hard-timeout-reached",
]
Notice = Literal[
    "metadata-only-content-not-opened",
    "embedded-production-metadata-not-inspected",
    "provider-sync-not-attested",
    "inventory-does-not-authorize-eviction",
    "candidate-output-truncated",
    "inventory-incomplete",
    "worker-hard-timeout",
    "inventory-issues-truncated",
]
IssueKind = Literal[
    "read-directory-failed",
    "read-entry-failed",
    "read-metadata-failed",
    "symlink-skipped",
    "unsupported-entry-type",
    "allocation-evidence-unavailable",
]
IssueReason = Literal[
    "not-found",
    "permission-denied",
    "connection-refused",
    "connection-reset",
    "connection-aborted",
    "not-connected",
    "address-in-use",
    "address-unavailable",
    "broken-pipe",
    "already-exists",
    "would-block",
    "invalid-input",
    "invalid-data",
    "timed-out",
    "write-zero",
    "interrupted",
    "unsupported",
    "unexpected-eof",
    "out-of-memory",
    "other-io-error",
    "policy-not-followed",
    "policy-not-file-or-directory",
    "platform-unsupported",
]


def _validate_bounded_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{field_name} contains a control character")
    return value


def _saturating_u64_sum(values: list[int]) -> int:
    return min(sum(values), MAX_U64)


def _lexical_absolute_path(
    value: str,
    field_name: str,
) -> tuple[Literal["posix", "windows"], PurePosixPath | PureWindowsPath]:
    _validate_bounded_text(value, field_name)
    if len(value.encode("utf-8")) > MAX_PATH_UTF8_BYTES:
        raise ValueError(f"{field_name} exceeds the UTF-8 byte limit")
    if value.startswith("/"):
        path: PurePosixPath | PureWindowsPath = PurePosixPath(value)
        style: Literal["posix", "windows"] = "posix"
    elif re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
        path = PureWindowsPath(value)
        style = "windows"
    else:
        raise ValueError(f"{field_name} must be absolute")
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{field_name} is not a safe absolute path")
    return style, path


class StrictAllocationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CloudLocalInventoryOptions(StrictAllocationModel):
    min_allocated_bytes: U64
    max_entries: Annotated[int, Field(ge=1, le=1_000_000)]
    max_results: Annotated[int, Field(ge=1, le=10_000)]
    max_depth: Annotated[int, Field(ge=0, le=64)]
    max_duration_ms: Annotated[int, Field(ge=1, le=300_000)]
    max_issues: Annotated[int, Field(ge=1, le=1_000)] | None = None


class CloudLocalInventoryIssue(StrictAllocationModel):
    relative_scope: BoundedText | None
    kind: IssueKind
    reason: IssueReason

    @field_validator("relative_scope")
    @classmethod
    def validate_relative_scope_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _validate_bounded_text(value, "issue.relative_scope")
        if len(value.encode("utf-8")) > MAX_PATH_UTF8_BYTES:
            raise ValueError("issue.relative_scope exceeds the UTF-8 byte limit")
        return value

    @model_validator(mode="after")
    def validate_kind_reason_binding(self) -> Self:
        read_kinds = {
            "read-directory-failed",
            "read-entry-failed",
            "read-metadata-failed",
        }
        io_reasons = {
            "not-found",
            "permission-denied",
            "connection-refused",
            "connection-reset",
            "connection-aborted",
            "not-connected",
            "address-in-use",
            "address-unavailable",
            "broken-pipe",
            "already-exists",
            "would-block",
            "invalid-input",
            "invalid-data",
            "timed-out",
            "write-zero",
            "interrupted",
            "unsupported",
            "unexpected-eof",
            "out-of-memory",
            "other-io-error",
        }
        expected_policy_reason = {
            "symlink-skipped": "policy-not-followed",
            "unsupported-entry-type": "policy-not-file-or-directory",
            "allocation-evidence-unavailable": "platform-unsupported",
        }
        if self.kind in read_kinds:
            if self.reason not in io_reasons:
                raise ValueError("read issue requires a stable I/O reason")
        elif self.reason != expected_policy_reason[self.kind]:
            raise ValueError("policy issue reason contradicts its kind")
        if self.relative_scope is None and self.kind not in {
            "read-directory-failed",
            "read-entry-failed",
        }:
            raise ValueError("entry-specific issue requires a relative scope")
        return self


class CloudLocalAllocationCandidate(StrictAllocationModel):
    path: BoundedText
    logical_bytes: U64
    allocated_bytes: Annotated[int, Field(ge=1, le=MAX_U64)]
    filesystem_created_ms: EpochMilliseconds | None
    filesystem_modified_ms: EpochMilliseconds | None
    allocation_evidence: Literal["filesystem:st-blocks-512"]
    content_opened: Literal[False]
    embedded_metadata_inspected: Literal[False]
    provider_sync_attested: Literal[False]
    eviction_blockers: tuple[
        Literal["provider-sync-unverified"],
        Literal["human-eviction-approval-required"],
    ]

    @field_validator("path")
    @classmethod
    def validate_path_text(cls, value: str) -> str:
        _lexical_absolute_path(value, "candidate.path")
        return value


class DiskSageCloudLocalAllocationInventory(StrictAllocationModel):
    version: Literal[1, 2]
    cloud_root_id: ShortText
    provider: CloudProvider
    account_scope: CloudAccountScope
    cloud_root: BoundedText
    observed_at_ms: EpochMilliseconds
    options: CloudLocalInventoryOptions
    visited_entries: U64
    visited_files: U64
    visited_directories: U64
    skipped_entries: U64
    issues: (
        Annotated[list[CloudLocalInventoryIssue], Field(max_length=1_000)] | None
    ) = None
    issues_truncated: bool | None = None
    allocated_candidate_bytes: U64
    candidates: list[CloudLocalAllocationCandidate] = Field(max_length=10_000)
    results_truncated: bool
    evidence_complete: bool
    stop_reasons: list[StopReason] = Field(max_length=6)
    notices: list[Notice] = Field(min_length=4, max_length=8)

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value not in {1, 2}:
            raise ValueError("version must be integer 1 or 2")
        return value

    @field_validator("cloud_root_id", "cloud_root")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return _validate_bounded_text(value, "cloud_local_allocation")

    @field_validator("cloud_root")
    @classmethod
    def validate_cloud_root(cls, value: str) -> str:
        _lexical_absolute_path(value, "cloud_root")
        return value

    @model_validator(mode="after")
    def validate_inventory_bindings(self) -> Self:
        if self.visited_entries > self.options.max_entries:
            raise ValueError("visited entries exceed the declared bound")
        if self.visited_files + self.visited_directories > self.visited_entries:
            raise ValueError("visited entry counters are inconsistent")
        if len(self.candidates) > self.options.max_results:
            raise ValueError("candidate output exceeds the declared result bound")
        if len(self.candidates) > self.visited_files:
            raise ValueError("candidate count exceeds visited files")
        if len(self.stop_reasons) != len(set(self.stop_reasons)):
            raise ValueError("stop reasons must be unique")

        root_style, root_path = _lexical_absolute_path(self.cloud_root, "cloud_root")
        candidate_paths: set[tuple[str, str]] = set()
        visible_allocations: list[int] = []
        for candidate in self.candidates:
            candidate_style, candidate_path = _lexical_absolute_path(
                candidate.path,
                "candidate.path",
            )
            if candidate_style != root_style:
                raise ValueError("candidate path style differs from cloud root")
            try:
                relative = candidate_path.relative_to(root_path)
            except ValueError as error:
                raise ValueError("candidate is outside the cloud root") from error
            if not relative.parts:
                raise ValueError("candidate cannot be the cloud root")
            path_key = str(candidate_path)
            if candidate_style == "windows":
                path_key = path_key.casefold()
            key = (candidate_style, path_key)
            if key in candidate_paths:
                raise ValueError("candidate paths must be unique")
            candidate_paths.add(key)
            if candidate.allocated_bytes < self.options.min_allocated_bytes:
                raise ValueError("candidate is below the allocation threshold")
            visible_allocations.append(candidate.allocated_bytes)

        if self.version == 1:
            if (
                self.options.max_issues is not None
                or self.issues is not None
                or self.issues_truncated is not None
            ):
                raise ValueError("version 1 must not contain version 2 issue fields")
        else:
            if (
                self.options.max_issues is None
                or self.issues is None
                or self.issues_truncated is None
            ):
                raise ValueError("version 2 requires bounded issue evidence")
            if len(self.issues) > self.options.max_issues:
                raise ValueError("issue output exceeds the declared bound")
            if self.issues_truncated:
                if len(
                    self.issues
                ) != self.options.max_issues or self.skipped_entries <= len(
                    self.issues
                ):
                    raise ValueError("truncated issue output does not fill its bound")
            elif self.skipped_entries != len(self.issues):
                raise ValueError("complete issue output does not account for skips")

            read_issue_present = False
            allocation_issue_present = False
            for issue in self.issues:
                if issue.relative_scope is not None:
                    issue_path: PurePosixPath | PureWindowsPath
                    if root_style == "posix":
                        issue_path = PurePosixPath(issue.relative_scope)
                    else:
                        issue_path = PureWindowsPath(issue.relative_scope)
                    if issue_path.is_absolute() or any(
                        part in {".", ".."} for part in issue_path.parts
                    ):
                        raise ValueError("issue scope is not a safe relative path")
                if issue.kind.startswith("read-"):
                    read_issue_present = True
                if issue.kind == "allocation-evidence-unavailable":
                    allocation_issue_present = True
            entry_errors_stopped = "entry-errors" in self.stop_reasons
            if read_issue_present and not entry_errors_stopped:
                raise ValueError("entry error stop contradicts issue evidence")
            if (
                entry_errors_stopped
                and not read_issue_present
                and not self.issues_truncated
            ):
                raise ValueError("entry error stop contradicts issue evidence")
            allocation_stopped = (
                "allocated-byte-evidence-unavailable" in self.stop_reasons
            )
            if allocation_issue_present and not allocation_stopped:
                raise ValueError("allocation stop contradicts issue evidence")
            if (
                allocation_stopped
                and not allocation_issue_present
                and not self.issues_truncated
            ):
                raise ValueError("allocation stop contradicts issue evidence")

        visible_allocated_bytes = _saturating_u64_sum(visible_allocations)
        if visible_allocated_bytes > self.allocated_candidate_bytes:
            raise ValueError("visible candidate allocation exceeds the inventory total")
        if not self.results_truncated and (
            visible_allocated_bytes != self.allocated_candidate_bytes
        ):
            raise ValueError(
                "complete candidate output does not match the inventory total"
            )
        if self.results_truncated and len(self.candidates) != self.options.max_results:
            raise ValueError("truncated output must fill the declared result bound")

        expected_complete = not self.stop_reasons and self.skipped_entries == 0
        if self.evidence_complete != expected_complete:
            raise ValueError("evidence completeness contradicts traversal counters")

        expected_notices = list(BASE_NOTICES)
        if self.results_truncated:
            expected_notices.append("candidate-output-truncated")
        if not self.evidence_complete:
            expected_notices.append("inventory-incomplete")
        hard_timeout = self.stop_reasons == ["hard-timeout-reached"]
        if hard_timeout:
            expected_notices.append("worker-hard-timeout")
        if self.version == 2 and self.issues_truncated:
            expected_notices.append("inventory-issues-truncated")
        if self.notices != expected_notices:
            raise ValueError("inventory notices contradict the report state")

        if "max-entries-reached" in self.stop_reasons and (
            self.visited_entries != self.options.max_entries
        ):
            raise ValueError("entry-bound stop does not match visited entries")
        if "entry-errors" in self.stop_reasons and self.skipped_entries == 0:
            raise ValueError("entry error stop lacks a skipped entry")
        if (
            "allocated-byte-evidence-unavailable" in self.stop_reasons
            and self.skipped_entries == 0
        ):
            raise ValueError("allocation evidence stop lacks a skipped entry")
        if "hard-timeout-reached" in self.stop_reasons and not hard_timeout:
            raise ValueError("hard timeout cannot be combined with cooperative stops")
        if hard_timeout and any(
            (
                self.visited_entries,
                self.visited_files,
                self.visited_directories,
                self.skipped_entries,
                self.allocated_candidate_bytes,
                len(self.candidates),
                int(self.results_truncated),
                len(self.issues or []),
                int(self.issues_truncated or False),
            )
        ):
            raise ValueError("hard timeout report must be empty and fail closed")
        return self


class CloudLocalAllocationValidationResponse(StrictAllocationModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    version: Literal[1, 2]
    evidence_kind: Literal["disksage.cloud-local-allocation-inventory"]


def validation_response(
    inventory: DiskSageCloudLocalAllocationInventory,
) -> CloudLocalAllocationValidationResponse:
    """Return a redacted acknowledgement without reflecting private paths or sizes."""

    return CloudLocalAllocationValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        version=inventory.version,
        evidence_kind="disksage.cloud-local-allocation-inventory",
    )
