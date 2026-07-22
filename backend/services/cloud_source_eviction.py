"""Strict, read-only validation of DiskSage cloud source eviction evidence.

The submitted envelope is evidence about an operation DiskSage already performed. This
module validates its schema and mutually bound claims only: it never opens a submitted
path and cannot independently prove an OS Trash call or recompute Rust BLAKE3 record IDs.
"""

from __future__ import annotations

import unicodedata
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.cloud_local_eviction import ActiveUseEvidence


U64_MAX = 18_446_744_073_709_551_615
MAX_PATH_UTF8_BYTES = 4_096
MAX_TEXT_UTF8_BYTES = 1_024

U64 = Annotated[int, Field(ge=0, le=U64_MAX)]
EpochMilliseconds = Annotated[int, Field(ge=0, le=U64_MAX)]
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
BoundedPath = Annotated[str, Field(min_length=1, max_length=4_096)]
BoundedText = Annotated[str, Field(min_length=1, max_length=1_024)]
ReasonCode = Annotated[str, Field(min_length=1, max_length=128)]
CloudProvider = Literal["icloud", "onedrive", "google-drive"]
SyncEvidenceKind = Literal["provider-api", "provider-native-status"]


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


def _is_within_or_equal(path: PurePosixPath, root: PurePosixPath) -> bool:
    if path == root:
        return True
    try:
        return bool(path.relative_to(root).parts)
    except ValueError:
        return False


class StrictSourceEvictionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RemoteContentProof(StrictSourceEvictionModel):
    object_id: BoundedText
    revision: BoundedText
    algorithm: Literal["sha256", "quick-xor"]
    checksum: BoundedText
    location_bound: Literal[True]
    location_proof: BoundedText

    @field_validator("object_id", "revision", "checksum", "location_proof")
    @classmethod
    def validate_bounded_text(cls, value: str) -> str:
        return _validate_text(
            value,
            "remote_content",
            max_utf8_bytes=MAX_TEXT_UTF8_BYTES,
        )


class ProviderSyncEvidence(StrictSourceEvictionModel):
    receipt_id: Hex64
    provider: CloudProvider
    destination: BoundedPath
    observed_bytes: U64
    destination_blake3: Hex64
    confirmed_at_ms: EpochMilliseconds
    kind: SyncEvidenceKind
    evidence_id: BoundedText
    sync_complete: Literal[True]
    remote_content: RemoteContentProof | None

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        return _validate_text(
            value,
            "evidence_id",
            max_utf8_bytes=MAX_TEXT_UTF8_BYTES,
        )

    @model_validator(mode="after")
    def validate_provider_proof(self) -> Self:
        _absolute_posix_path(self.destination, "evidence.destination")
        if self.kind == "provider-native-status":
            if self.remote_content is not None:
                raise ValueError("provider-native evidence cannot contain remote proof")
            return self

        if self.provider == "icloud" or self.remote_content is None:
            raise ValueError("provider API evidence is unsupported or incomplete")
        expected_algorithm = "quick-xor" if self.provider == "onedrive" else "sha256"
        expected_prefix = (
            "onedrive-path-v1:"
            if self.provider == "onedrive"
            else "google-drive-parent-chain-v1:"
        )
        if self.remote_content.algorithm != expected_algorithm:
            raise ValueError("provider API checksum algorithm is inconsistent")
        digest = self.remote_content.location_proof.removeprefix(expected_prefix)
        if (
            digest == self.remote_content.location_proof
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("provider API location proof is inconsistent")
        return self


class ProviderSyncEvidenceRecord(StrictSourceEvictionModel):
    version: Literal[1]
    record_id: Hex64
    evidence: ProviderSyncEvidence

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("version must be integer 1")
        return value


class ProviderSyncTimelinessAssessment(StrictSourceEvictionModel):
    state: Literal["complete"]
    pending_age_ms: Literal[0]
    overdue_after_ms: Literal[86_400_000]
    reason_codes: list[ReasonCode] = Field(max_length=0)

    @field_validator("pending_age_ms", "overdue_after_ms", mode="before")
    @classmethod
    def validate_exact_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("timeliness values must be integers")
        return value


class LocalEvictionPermit(StrictSourceEvictionModel):
    receipt_id: Hex64
    provider: CloudProvider
    source: BoundedPath
    destination: BoundedPath
    bytes: U64
    blake3: Hex64
    approved_at_ms: EpochMilliseconds
    evidence_kind: SyncEvidenceKind
    evidence_id: BoundedText
    evidence_record_id: Hex64

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        return _validate_text(
            value,
            "permit.evidence_id",
            max_utf8_bytes=MAX_TEXT_UTF8_BYTES,
        )


class CloudSourceEvictionAttestation(StrictSourceEvictionModel):
    evidence: ProviderSyncEvidence
    assessment: ProviderSyncTimelinessAssessment
    evidence_record: ProviderSyncEvidenceRecord
    evidence_path: BoundedPath
    permit: LocalEvictionPermit
    blockers: list[ReasonCode] = Field(max_length=0)


class CloudSourceEvictionApproval(StrictSourceEvictionModel):
    version: Literal[1]
    approval_id: Hex64
    receipt_id: Hex64
    evidence_record_id: Hex64
    approved_at_ms: EpochMilliseconds
    approved_by: Annotated[str, Field(min_length=7, max_length=256)]
    rationale: Annotated[str, Field(min_length=1, max_length=1_024)]
    active_use_observed_at_ms: EpochMilliseconds
    active_use: ActiveUseEvidence

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
            max_utf8_bytes=MAX_TEXT_UTF8_BYTES,
        )

    @model_validator(mode="after")
    def validate_safe_active_use(self) -> Self:
        if (
            not self.active_use.evidence_complete
            or self.active_use.active
            or self.active_use.observed_pids
            or self.active_use.results_truncated
            or self.active_use.error is not None
        ):
            raise ValueError("source eviction requires complete inactive-use evidence")
        if self.active_use_observed_at_ms > self.approved_at_ms:
            raise ValueError("active-use observation cannot postdate approval")
        return self


class CloudEvictionResult(StrictSourceEvictionModel):
    action: Literal["trash-verified-cloud-source"]
    receipt_id: Hex64
    intent_id: Hex64
    completion_id: Hex64
    evidence_record_id: Hex64
    approval_id: Hex64
    source: BoundedPath
    staged_source: BoundedPath
    intent_path: BoundedPath
    completion_path: BoundedPath
    source_trashed: bool
    reconciled_after_interruption: bool
    already_completed: bool

    @model_validator(mode="after")
    def validate_result_state(self) -> Self:
        expected_source_trashed = (
            not self.already_completed and not self.reconciled_after_interruption
        )
        if self.source_trashed != expected_source_trashed:
            raise ValueError("source Trash state is inconsistent")
        return self


class DiskSageCloudSourceEvictionOutput(StrictSourceEvictionModel):
    action: Literal["attest-approve-and-trash-verified-cloud-source"]
    attestation: CloudSourceEvictionAttestation
    approval: CloudSourceEvictionApproval
    approval_path: BoundedPath
    eviction: CloudEvictionResult

    @model_validator(mode="after")
    def validate_claim_bindings(self) -> Self:
        evidence = self.attestation.evidence
        record = self.attestation.evidence_record
        permit = self.attestation.permit
        approval = self.approval
        eviction = self.eviction

        if record.evidence != evidence:
            raise ValueError("evidence record does not bind the attestation evidence")
        if (
            permit.receipt_id != evidence.receipt_id
            or permit.provider != evidence.provider
            or permit.destination != evidence.destination
            or permit.bytes != evidence.observed_bytes
            or permit.blake3 != evidence.destination_blake3
            or permit.approved_at_ms != evidence.confirmed_at_ms
            or permit.evidence_kind != evidence.kind
            or permit.evidence_id != evidence.evidence_id
            or permit.evidence_record_id != record.record_id
        ):
            raise ValueError("eviction permit does not bind provider evidence")
        if permit.source == permit.destination:
            raise ValueError("source and destination must be distinct")
        if (
            approval.receipt_id != permit.receipt_id
            or approval.evidence_record_id != permit.evidence_record_id
            or approval.active_use_observed_at_ms < permit.approved_at_ms
        ):
            raise ValueError("human approval does not bind the permit")
        if (
            eviction.receipt_id != permit.receipt_id
            or eviction.evidence_record_id != permit.evidence_record_id
            or eviction.approval_id != approval.approval_id
            or eviction.source != permit.source
        ):
            raise ValueError("eviction result does not bind the approval")

        source = _absolute_posix_path(permit.source, "permit.source")
        destination = _absolute_posix_path(permit.destination, "permit.destination")
        evidence_path = _absolute_posix_path(
            self.attestation.evidence_path,
            "attestation.evidence_path",
        )
        approval_path = _absolute_posix_path(self.approval_path, "approval_path")
        staged_source = _absolute_posix_path(
            eviction.staged_source,
            "eviction.staged_source",
        )
        intent_path = _absolute_posix_path(eviction.intent_path, "eviction.intent_path")
        completion_path = _absolute_posix_path(
            eviction.completion_path,
            "eviction.completion_path",
        )

        if source.name in {"", ".", ".."} or source.parent == source:
            raise ValueError("source must have a safe basename and parent")
        expected_staging_dir = source.parent / f".disksage-evict-{permit.receipt_id}"
        if staged_source != expected_staging_dir / source.name:
            raise ValueError("staged source is not receipt-bound")
        if evidence_path.name != (
            f"{evidence.receipt_id}-{evidence.confirmed_at_ms:020}-"
            f"{record.record_id}.json"
        ):
            raise ValueError("provider evidence filename is not record-bound")
        if approval_path.name != f"{approval.approval_id}.approval.json":
            raise ValueError("approval filename is not approval-bound")
        if intent_path.name != f"{permit.receipt_id}.intent.json":
            raise ValueError("intent filename is not receipt-bound")
        if completion_path.name != f"{permit.receipt_id}.complete.json":
            raise ValueError("completion filename is not receipt-bound")
        if intent_path.parent != completion_path.parent:
            raise ValueError("intent and completion records must share a control root")

        data_paths = (source, destination, expected_staging_dir, staged_source)
        control_paths = (evidence_path, approval_path, intent_path, completion_path)
        if len(set(control_paths)) != len(control_paths):
            raise ValueError("control records must be distinct")
        for control_path in control_paths:
            if any(
                _is_within_or_equal(control_path, data_path) for data_path in data_paths
            ):
                raise ValueError(
                    "control record overlaps source, destination, or staging"
                )
        return self


class CloudSourceEvictionValidationResponse(StrictSourceEvictionModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    version: Literal[1]
    evidence_kind: Literal["disksage.cloud-source-eviction"]
    evidence_stage: Literal["execution"]


def validation_response(
    evidence: DiskSageCloudSourceEvictionOutput,
) -> CloudSourceEvictionValidationResponse:
    """Return a redacted acknowledgement without paths, sizes, IDs, or identities."""

    del evidence
    return CloudSourceEvictionValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        version=1,
        evidence_kind="disksage.cloud-source-eviction",
        evidence_stage="execution",
    )
