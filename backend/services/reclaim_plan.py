"""Strict claim-consistency validation for DiskSage reclaim-plan evidence."""

from __future__ import annotations

import unicodedata
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


U64_MAX = 18_446_744_073_709_551_615
MAX_RECLAIM_PATHS = 1_000
MAX_RECLAIM_PATH_UTF8_BYTES = 4_096

U64 = Annotated[int, Field(ge=0, le=U64_MAX)]
BoundedPath = Annotated[str, Field(min_length=1, max_length=4096)]
BoundedReasonCode = Annotated[str, Field(min_length=1, max_length=128)]


def _validate_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{field_name} contains a control character")
    return value


def _expected_reason_codes(
    operation: str,
    *,
    allocation_available: bool,
) -> list[str]:
    reasons = [
        "physical-reclaimability-unverified",
        "shared-extents-or-clones-unproven",
        (
            "allocated-bytes-are-not-reclaimability-proof"
            if allocation_available
            else "allocated-size-unavailable"
        ),
    ]
    if operation == "trash":
        reasons.append("trash-retains-bytes-until-emptied")
    return reasons


def _saturating_u64_sum(values: list[int]) -> int:
    return min(sum(values), U64_MAX)


class StrictReclaimEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReclaimEstimate(StrictReclaimEvidenceModel):
    logical_bytes: U64
    allocated_bytes: U64 | None
    physically_reclaimable_bytes: None
    status: Literal["unverified"]
    reason_codes: list[BoundedReasonCode] = Field(min_length=3, max_length=4)


class PathReclaimEstimate(StrictReclaimEvidenceModel):
    path: BoundedPath
    kind: Literal["file", "directory"]
    files: U64
    dirs: U64
    skipped: U64
    estimate: ReclaimEstimate

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        value = _validate_text(value, "path")
        if len(value.encode("utf-8")) > MAX_RECLAIM_PATH_UTF8_BYTES:
            raise ValueError(
                f"path must not exceed {MAX_RECLAIM_PATH_UTF8_BYTES} UTF-8 bytes"
            )
        return value

    @model_validator(mode="after")
    def validate_kind_counts(self) -> Self:
        if self.kind == "file" and (
            self.files != 1 or self.dirs != 0 or self.skipped != 0
        ):
            raise ValueError(
                "file roots require one file, zero directories, and zero skipped entries"
            )
        if self.kind == "directory" and self.dirs < 1:
            raise ValueError("directory roots require at least one directory")
        return self


class DiskSageReclaimPlanEnvelope(StrictReclaimEvidenceModel):
    schema_kind: Literal["disksage.reclaim-plan"]
    schema_version: Literal[1]
    operation: Literal["trash", "delete"]
    paths: list[PathReclaimEstimate] = Field(
        min_length=1,
        max_length=MAX_RECLAIM_PATHS,
    )
    totals: ReclaimEstimate

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_exact_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be integer 1")
        return value

    @model_validator(mode="after")
    def validate_claim_bindings(self) -> Self:
        path_names = [
            unicodedata.normalize("NFC", entry.path).casefold()
            for entry in self.paths
        ]
        if len(path_names) != len(set(path_names)):
            raise ValueError("paths must be unique")

        estimates = [entry.estimate for entry in self.paths]
        for estimate in [*estimates, self.totals]:
            expected_reasons = _expected_reason_codes(
                self.operation,
                allocation_available=estimate.allocated_bytes is not None,
            )
            if estimate.reason_codes != expected_reasons:
                raise ValueError("reason codes do not match DiskSage semantics")

        expected_logical = _saturating_u64_sum(
            [estimate.logical_bytes for estimate in estimates]
        )
        if self.totals.logical_bytes != expected_logical:
            raise ValueError("logical byte total is inconsistent")

        allocations = [estimate.allocated_bytes for estimate in estimates]
        allocation_available = [value is not None for value in allocations]
        if not all(allocation_available) and any(allocation_available):
            raise ValueError("path allocation availability must be consistent")

        if all(allocation_available):
            if self.totals.allocated_bytes is None:
                raise ValueError("allocated byte total is unexpectedly unavailable")
            path_allocated_sum = _saturating_u64_sum(
                [value for value in allocations if value is not None]
            )
            largest_path_allocation = max(
                value for value in allocations if value is not None
            )
            if self.totals.allocated_bytes < largest_path_allocation:
                raise ValueError("allocated byte total is below a path observation")
            if self.totals.allocated_bytes > path_allocated_sum:
                raise ValueError("allocated byte total exceeds path observations")
        elif self.totals.allocated_bytes is not None:
            raise ValueError("allocated byte total is unexpectedly available")

        return self


class ReclaimPlanValidationResponse(StrictReclaimEvidenceModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    schema_version: Literal[1]
    schema_kind: Literal["disksage.reclaim-plan"]


def reclaim_plan_validation_response(
    envelope: DiskSageReclaimPlanEnvelope,
) -> ReclaimPlanValidationResponse:
    """Return no submitted paths, counts, or byte observations."""

    return ReclaimPlanValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        schema_version=envelope.schema_version,
        schema_kind=envelope.schema_kind,
    )
