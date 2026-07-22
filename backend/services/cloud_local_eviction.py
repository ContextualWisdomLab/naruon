"""Strict, database-independent validation of DiskSage iCloud local eviction evidence."""

from __future__ import annotations

import unicodedata
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


U64_MAX = 18_446_744_073_709_551_615
MAX_PATH_UTF8_BYTES = 4_096
MAX_ACTIVE_PIDS = 64
MAX_RATIONALE_UTF8_BYTES = 1_024

U64 = Annotated[int, Field(ge=0, le=U64_MAX)]
EpochMilliseconds = Annotated[int, Field(ge=0, le=U64_MAX)]
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
BoundedPath = Annotated[str, Field(min_length=1, max_length=4_096)]
ReasonCode = Annotated[str, Field(min_length=1, max_length=128)]

PLAN_NOTICES = [
    "file-content-not-opened",
    "embedded-metadata-not-required-for-local-cache-eviction",
    "cloud-object-must-remain-present",
    "allocated-byte-reduction-is-not-volume-free-space-proof",
]
RESULT_NOTICES = [
    "cloud-object-delete-not-requested",
    "observed-allocation-reduction-is-not-volume-free-space-proof",
]


def _validate_text(value: str, field_name: str, *, max_utf8_bytes: int) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if len(value.encode("utf-8")) > max_utf8_bytes:
        raise ValueError(f"{field_name} exceeds its UTF-8 byte limit")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{field_name} contains a control character")
    return value


def _absolute_posix_path(value: str, field_name: str) -> PurePosixPath:
    _validate_text(value, field_name, max_utf8_bytes=MAX_PATH_UTF8_BYTES)
    path = PurePosixPath(value)
    if not value.startswith("/") or not path.is_absolute():
        raise ValueError(f"{field_name} must be an absolute POSIX path")
    if any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{field_name} is not a safe absolute path")
    return path


def _is_within(path: PurePosixPath, root: PurePosixPath) -> bool:
    try:
        return bool(path.relative_to(root).parts)
    except ValueError:
        return False


class StrictEvictionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class IcloudLocalState(StrictEvictionModel):
    is_ubiquitous: bool
    is_uploaded: bool
    is_uploading: bool
    is_downloading: bool
    downloading_status_current: bool
    has_unresolved_conflicts: bool
    is_excluded_from_sync: bool


class ActiveUseEvidence(StrictEvictionModel):
    method: Literal["lsof-fp+ps-command"]
    evidence_complete: bool
    active: bool
    observed_pids: list[Annotated[int, Field(ge=1, le=4_294_967_295)]] = Field(
        max_length=MAX_ACTIVE_PIDS
    )
    results_truncated: bool
    error: Annotated[str, Field(min_length=1, max_length=512)] | None

    @model_validator(mode="after")
    def validate_active_use_bindings(self) -> Self:
        if self.observed_pids != sorted(set(self.observed_pids)):
            raise ValueError("active-use PIDs must be unique and sorted")
        if self.active != bool(self.observed_pids):
            raise ValueError("active-use flag contradicts observed PIDs")
        expected_complete = not self.results_truncated and self.error is None
        if self.evidence_complete != expected_complete:
            raise ValueError("active-use completeness contradicts evidence state")
        return self


class IcloudLocalEvictionPlan(StrictEvictionModel):
    version: Literal[1]
    provider: Literal["icloud"]
    account_scope: Literal["personal", "organization", "shared", "unknown"]
    cloud_root: BoundedPath
    path: BoundedPath
    logical_bytes: U64
    allocated_bytes: U64
    filesystem_modified_ms: EpochMilliseconds
    observed_at_ms: EpochMilliseconds
    icloud_state: IcloudLocalState
    active_use: ActiveUseEvidence
    plan_fingerprint: Hex64
    eligible_after_human_approval: bool
    blockers: list[ReasonCode] = Field(min_length=1, max_length=11)
    notices: list[ReasonCode] = Field(min_length=4, max_length=4)

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("version must be integer 1")
        return value

    @model_validator(mode="after")
    def validate_plan_bindings(self) -> Self:
        root = _absolute_posix_path(self.cloud_root, "cloud_root")
        path = _absolute_posix_path(self.path, "path")
        if not _is_within(path, root):
            raise ValueError("path must be a file below cloud_root")

        expected: list[str] = []
        if self.allocated_bytes == 0:
            expected.append("icloud-local-copy-not-allocated")
        if not self.icloud_state.is_ubiquitous:
            expected.append("icloud-item-not-ubiquitous")
        if not self.icloud_state.is_uploaded:
            expected.append("icloud-upload-not-confirmed")
        if self.icloud_state.is_uploading:
            expected.append("icloud-upload-still-running")
        if self.icloud_state.is_downloading:
            expected.append("icloud-download-running")
        if not self.icloud_state.downloading_status_current:
            expected.append("icloud-current-version-unconfirmed")
        if self.icloud_state.has_unresolved_conflicts:
            expected.append("icloud-unresolved-conflict")
        if self.icloud_state.is_excluded_from_sync:
            expected.append("icloud-item-excluded-from-sync")
        if not self.active_use.evidence_complete:
            expected.append("active-use-evidence-incomplete")
        if self.active_use.active:
            expected.append("active-file-use-detected")

        expected_eligible = not expected
        expected.append("human-local-eviction-approval-required")
        if self.eligible_after_human_approval != expected_eligible:
            raise ValueError("eligibility contradicts the fail-closed plan state")
        if self.blockers != expected:
            raise ValueError("blockers contradict the fail-closed plan state")
        if self.notices != PLAN_NOTICES:
            raise ValueError("plan notices contradict the DiskSage contract")
        return self


class IcloudLocalEvictionApproval(StrictEvictionModel):
    version: Literal[1]
    approval_id: Hex64
    plan_fingerprint: Hex64
    approved_at_ms: EpochMilliseconds
    approved_by: Annotated[str, Field(min_length=7, max_length=256)]
    rationale: Annotated[str, Field(min_length=1, max_length=1_024)]

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("version must be integer 1")
        return value

    @field_validator("approved_by")
    @classmethod
    def validate_human_attribution(cls, value: str) -> str:
        _validate_text(value, "approved_by", max_utf8_bytes=256)
        if not value.startswith("human:") or not value.removeprefix("human:").strip():
            raise ValueError("approved_by must contain human attribution")
        return value

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        return _validate_text(
            value,
            "rationale",
            max_utf8_bytes=MAX_RATIONALE_UTF8_BYTES,
        )


class IcloudLocalEvictionResult(StrictEvictionModel):
    version: Literal[1]
    result_id: Hex64
    plan_fingerprint: Hex64
    approval_id: Hex64
    path: BoundedPath
    requested_at_ms: EpochMilliseconds
    allocated_bytes_before: U64
    allocated_bytes_after: U64
    observed_allocation_reduction_bytes: U64
    eviction_request_succeeded: Literal[True]
    cloud_item_path_retained: bool
    is_ubiquitous_after: bool
    local_allocation_reduction_verified: bool
    verification_complete: bool
    verification_blockers: list[ReasonCode] = Field(max_length=3)
    notices: list[ReasonCode] = Field(min_length=2, max_length=2)

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("version must be integer 1")
        return value

    @model_validator(mode="after")
    def validate_result_claims(self) -> Self:
        _absolute_posix_path(self.path, "result.path")
        expected_reduction = max(
            self.allocated_bytes_before - self.allocated_bytes_after,
            0,
        )
        reduced = self.allocated_bytes_after < self.allocated_bytes_before
        if self.observed_allocation_reduction_bytes != expected_reduction:
            raise ValueError("observed allocation reduction is inconsistent")
        if self.local_allocation_reduction_verified != reduced:
            raise ValueError("allocation verification contradicts observed bytes")

        expected_blockers: list[str] = []
        if not self.cloud_item_path_retained:
            expected_blockers.append("icloud-cloud-item-path-not-retained")
        if not self.is_ubiquitous_after:
            expected_blockers.append("icloud-ubiquitous-identity-not-retained")
        if not reduced:
            expected_blockers.append("local-allocation-reduction-unverified")
        if self.verification_blockers != expected_blockers:
            raise ValueError("result blockers contradict post-eviction evidence")
        if self.verification_complete != (not expected_blockers):
            raise ValueError("result completeness contradicts post-eviction evidence")
        if self.notices != RESULT_NOTICES:
            raise ValueError("result notices contradict the DiskSage contract")
        return self


class IcloudLocalEvictionPlanOutput(StrictEvictionModel):
    action: Literal["plan-icloud-local-eviction"]
    mutation_executed: Literal[False]
    plan: IcloudLocalEvictionPlan


class IcloudLocalEvictionExecuteOutput(StrictEvictionModel):
    action: Literal["evict-icloud-local-copy"]
    mutation_executed: Literal[True]
    plan: IcloudLocalEvictionPlan
    approval: IcloudLocalEvictionApproval
    approval_record: BoundedPath
    result: IcloudLocalEvictionResult
    result_record: BoundedPath

    @model_validator(mode="after")
    def validate_execution_bindings(self) -> Self:
        if not self.plan.eligible_after_human_approval or self.plan.blockers != [
            "human-local-eviction-approval-required"
        ]:
            raise ValueError("execution requires an otherwise eligible plan")
        if self.approval.plan_fingerprint != self.plan.plan_fingerprint:
            raise ValueError("approval is not bound to the plan")
        if self.approval.approved_at_ms < self.plan.observed_at_ms:
            raise ValueError("approval predates the plan")
        if self.result.plan_fingerprint != self.plan.plan_fingerprint:
            raise ValueError("result is not bound to the plan")
        if self.result.approval_id != self.approval.approval_id:
            raise ValueError("result is not bound to the approval")
        if self.result.path != self.plan.path:
            raise ValueError("result path differs from the approved plan")
        if self.result.allocated_bytes_before != self.plan.allocated_bytes:
            raise ValueError("result before-allocation differs from the plan")
        if self.result.requested_at_ms < self.approval.approved_at_ms:
            raise ValueError("eviction request predates approval")

        root = _absolute_posix_path(self.plan.cloud_root, "cloud_root")
        approval_record = _absolute_posix_path(
            self.approval_record,
            "approval_record",
        )
        result_record = _absolute_posix_path(self.result_record, "result_record")
        if _is_within(approval_record, root) or _is_within(result_record, root):
            raise ValueError("evidence records must remain outside cloud data")
        if approval_record == result_record:
            raise ValueError("approval and result records must be distinct")
        if approval_record.name != f"{self.approval.approval_id}.approval.json":
            raise ValueError("approval record name is not bound to approval_id")
        if result_record.name != f"{self.result.result_id}.result.json":
            raise ValueError("result record name is not bound to result_id")
        return self


CloudLocalEvictionEvidence = Annotated[
    IcloudLocalEvictionPlanOutput | IcloudLocalEvictionExecuteOutput,
    Field(discriminator="action"),
]


class CloudLocalEvictionValidationResponse(StrictEvictionModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    version: Literal[1]
    evidence_kind: Literal["disksage.icloud-local-eviction"]
    evidence_stage: Literal["plan", "execution"]


def validation_response(
    evidence: IcloudLocalEvictionPlanOutput | IcloudLocalEvictionExecuteOutput,
) -> CloudLocalEvictionValidationResponse:
    """Return a redacted acknowledgement without paths, byte counts, or identities."""

    return CloudLocalEvictionValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        version=1,
        evidence_kind="disksage.icloud-local-eviction",
        evidence_stage=(
            "execution"
            if isinstance(evidence, IcloudLocalEvictionExecuteOutput)
            else "plan"
        ),
    )
