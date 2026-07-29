"""Strict claim-consistency validation for redacted DiskSage capacity evidence.

This contract does not call a cloud provider and cannot rederive DiskSage's provider-bound
evidence fingerprint. It validates the versioned shape, destination binding, provider semantics,
and the deterministic capacity arithmetic without persisting submitted observations.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


U64_MAX = 18_446_744_073_709_551_615

U64 = Annotated[int, Field(ge=0, le=U64_MAX)]
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ReasonCode = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,127}$")]
Provider = Literal["icloud", "onedrive", "google-drive"]
AccountScope = Literal["personal", "organization", "shared", "unknown"]
CapacityState = Literal[
    "available",
    "normal",
    "nearing",
    "critical",
    "exceeded",
    "unlimited",
    "unavailable",
]
EvidenceKind = Literal["provider-api", "provider-native-status", "unavailable"]


class StrictCapacityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CloudCapacitySnapshot(StrictCapacityModel):
    schema_version: Literal[3]
    provider: Provider
    account_scope: AccountScope | None
    evidence_kind: EvidenceKind
    observed_at_ms: U64
    total_bytes: U64 | None
    used_bytes: U64 | None
    remaining_bytes: U64 | None
    trashed_bytes: U64 | None
    max_upload_size_bytes: U64 | None
    state: CapacityState
    evidence_fingerprint: Hex64 | None
    unavailable_reason: ReasonCode | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_exact_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != 3:
            raise ValueError("capacity schema_version must be integer 3")
        return value

    @model_validator(mode="after")
    def validate_provider_shape(self) -> Self:
        byte_fields = (
            self.total_bytes,
            self.used_bytes,
            self.remaining_bytes,
            self.trashed_bytes,
            self.max_upload_size_bytes,
        )
        if self.evidence_kind == "unavailable":
            if (
                self.account_scope is not None
                or self.state != "unavailable"
                or any(value is not None for value in byte_fields)
                or self.evidence_fingerprint is not None
                or self.unavailable_reason is None
            ):
                raise ValueError("unavailable capacity shape is inconsistent")
            return self

        if self.evidence_fingerprint is None or self.unavailable_reason is not None:
            raise ValueError("available evidence binding is incomplete")

        if self.evidence_kind == "provider-native-status":
            expected_state = (
                "exceeded" if self.remaining_bytes == 0 else "available"
            )
            if (
                self.provider != "icloud"
                or self.account_scope != "personal"
                or self.remaining_bytes is None
                or self.total_bytes is not None
                or self.used_bytes is not None
                or self.trashed_bytes is not None
                or self.max_upload_size_bytes is not None
                or self.state != expected_state
            ):
                raise ValueError("provider-native capacity shape is inconsistent")
            return self

        if self.provider == "icloud":
            raise ValueError("iCloud provider API evidence is unsupported")
        if self.provider == "onedrive":
            self._validate_onedrive_shape()
        else:
            self._validate_google_drive_shape()
        return self

    def _validate_onedrive_shape(self) -> None:
        if (
            self.account_scope not in {"personal", "organization", "shared"}
            or self.total_bytes is None
            or self.used_bytes is None
            or self.remaining_bytes is None
            or self.remaining_bytes > self.total_bytes
            or self.max_upload_size_bytes is not None
            or self.state not in {"normal", "nearing", "critical", "exceeded"}
        ):
            raise ValueError("OneDrive capacity shape is inconsistent")

    def _validate_google_drive_shape(self) -> None:
        if (
            self.account_scope is not None
            or self.used_bytes is None
            or self.trashed_bytes is None
            or self.max_upload_size_bytes is None
        ):
            raise ValueError("Google Drive capacity shape is inconsistent")
        if self.total_bytes is None:
            if self.remaining_bytes is not None or self.state != "unlimited":
                raise ValueError("Google Drive unlimited shape is inconsistent")
            return

        expected_remaining = max(self.total_bytes - self.used_bytes, 0)
        if self.remaining_bytes != expected_remaining:
            raise ValueError("Google Drive remaining bytes are inconsistent")
        if self.used_bytes >= self.total_bytes:
            expected_state = "exceeded"
        elif expected_remaining * 100 < self.total_bytes:
            expected_state = "critical"
        elif expected_remaining * 10 < self.total_bytes:
            expected_state = "nearing"
        else:
            expected_state = "normal"
        if self.state != expected_state:
            raise ValueError("Google Drive capacity state is inconsistent")


class CloudCapacityAssessment(StrictCapacityModel):
    snapshot: CloudCapacitySnapshot
    requested_bytes: U64
    largest_candidate_bytes: U64
    reserve_bytes: U64
    required_bytes: U64 | None
    can_fit: bool | None
    blockers: list[ReasonCode] = Field(max_length=16)
    notices: list[ReasonCode] = Field(max_length=16)

    @model_validator(mode="after")
    def validate_assessment_arithmetic(self) -> Self:
        required_sum = self.requested_bytes + self.reserve_bytes
        expected_required = required_sum if required_sum <= U64_MAX else None
        blockers: list[str] = []
        notices: list[str] = []

        if self.snapshot.evidence_kind == "unavailable":
            blockers.append(
                self.snapshot.unavailable_reason or "cloud-capacity-unavailable"
            )
            expected_can_fit = None
        else:
            if expected_required is None:
                blockers.append("cloud-capacity-required-bytes-overflow")
            if self.snapshot.state == "exceeded":
                blockers.append("cloud-capacity-provider-state-exceeded")
            elif self.snapshot.state == "critical":
                notices.append("cloud-capacity-provider-state-critical")
            elif self.snapshot.state == "nearing":
                notices.append("cloud-capacity-provider-state-nearing")
            elif self.snapshot.state == "unlimited":
                notices.append("cloud-capacity-provider-reports-unlimited")
            if self.snapshot.provider == "google-drive":
                notices.append(
                    "google-capacity-may-reflect-pooled-organization-storage"
                )
            if (
                self.snapshot.max_upload_size_bytes is not None
                and self.largest_candidate_bytes
                > self.snapshot.max_upload_size_bytes
            ):
                blockers.append("cloud-max-upload-size-exceeded")

            if (
                expected_required is not None
                and self.snapshot.remaining_bytes is not None
            ):
                if expected_required > self.snapshot.remaining_bytes:
                    blockers.append("cloud-capacity-insufficient-with-reserve")
            elif not (
                expected_required is not None
                and self.snapshot.remaining_bytes is None
                and self.snapshot.state == "unlimited"
            ):
                blockers.append("cloud-capacity-remaining-unverified")
            blockers = sorted(set(blockers))
            expected_can_fit = not blockers

        notices = sorted(set(notices))
        if (
            self.required_bytes != expected_required
            or self.can_fit is not expected_can_fit
            or self.blockers != blockers
            or self.notices != notices
        ):
            raise ValueError("capacity assessment claims are inconsistent")
        return self


class DiskSageCloudCapacityEnvelope(StrictCapacityModel):
    schema_kind: Literal["disksage.cloud-capacity-assessment"]
    schema_version: Literal[1]
    decision_batch_fingerprint_version: Literal[1]
    decision_batch_fingerprint: Hex64
    provider: Provider
    destination_account_scope: AccountScope
    capacity: CloudCapacityAssessment

    @field_validator(
        "schema_version",
        "decision_batch_fingerprint_version",
        mode="before",
    )
    @classmethod
    def validate_exact_envelope_versions(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("envelope versions must be integer 1")
        return value

    @model_validator(mode="after")
    def validate_destination_binding(self) -> Self:
        snapshot = self.capacity.snapshot
        if snapshot.provider != self.provider:
            raise ValueError("capacity provider does not match the envelope")
        if (
            snapshot.account_scope is not None
            and snapshot.account_scope != self.destination_account_scope
        ):
            raise ValueError("capacity account scope does not match the destination")
        return self


class CloudCapacityValidationResponse(StrictCapacityModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    schema_version: Literal[1]
    schema_kind: Literal["disksage.cloud-capacity-assessment"]
    capacity_schema_version: Literal[3]


def cloud_capacity_validation_response(
    envelope: DiskSageCloudCapacityEnvelope,
) -> CloudCapacityValidationResponse:
    """Return fixed contract metadata without reflecting submitted evidence."""

    return CloudCapacityValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        schema_version=envelope.schema_version,
        schema_kind=envelope.schema_kind,
        capacity_schema_version=3,
    )
