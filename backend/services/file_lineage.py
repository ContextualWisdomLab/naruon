"""Strict validation contract for DiskSage general-file lineage evidence.

The RFC 822 lineage contract remains email-specific. This module accepts the distinct
``disksage.file-lineage`` v1 envelope without persisting provider paths or evidence identifiers.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EVIDENCE_PRECEDENCE = (
    "embedded_metadata",
    "explicit_filename_date",
    "filesystem_created_at",
    "filesystem_modified_at",
)

Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
BoundedText = Annotated[str, Field(min_length=1, max_length=4096)]
ShortText = Annotated[str, Field(min_length=1, max_length=1024)]
U64_MAX = 18_446_744_073_709_551_615
EpochMilliseconds = Annotated[int, Field(ge=0, le=U64_MAX)]
NonNegativeBytes = Annotated[int, Field(ge=0, le=U64_MAX)]
Confidence = Literal["high", "medium", "low"]
ReviewDisposition = Literal["approved", "held"]


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _validate_bounded_text(value: str, field_name: str) -> str:
    if _has_control_character(value):
        raise ValueError(f"{field_name} contains a control character")
    return value


def _relative_path_parts(value: str) -> tuple[str, ...]:
    _validate_bounded_text(value, "source_relative_path")
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise ValueError("source_relative_path must be relative")
    if "/" in value and "\\" in value:
        raise ValueError("source_relative_path cannot mix path separators")
    separator = "\\" if "\\" in value else "/"
    parts = tuple(value.split(separator))
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("source_relative_path contains an unsafe component")
    return parts


class StrictLineageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MetadataEvidence(StrictLineageModel):
    field: ShortText
    value: BoundedText
    source: ShortText
    confidence: Confidence

    @field_validator("field", "value", "source")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        return _validate_bounded_text(value, "metadata_evidence")


class FileProductionTimeLineage(StrictLineageModel):
    selected_value_ms: EpochMilliseconds
    selected_source: ShortText
    confidence: Confidence
    evidence_precedence: tuple[
        Literal["embedded_metadata"],
        Literal["explicit_filename_date"],
        Literal["filesystem_created_at"],
        Literal["filesystem_modified_at"],
    ]

    @field_validator("selected_source")
    @classmethod
    def validate_selected_source(cls, value: str) -> str:
        _validate_bounded_text(value, "selected_source")
        if not (
            value.startswith("embedded:")
            or value.startswith("filename:")
            or value in {"filesystem:created", "filesystem:modified-fallback"}
        ):
            raise ValueError("selected_source is not a supported evidence source")
        return value

    @field_validator("evidence_precedence")
    @classmethod
    def validate_evidence_precedence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != EVIDENCE_PRECEDENCE:
            raise ValueError("evidence_precedence does not match the v1 contract")
        return value


class FileFilesystemTimeLineage(StrictLineageModel):
    created_at_ms: EpochMilliseconds
    modified_at_ms: EpochMilliseconds


class FileReviewLineage(StrictLineageModel):
    candidate_fingerprint: Hex64
    review_fingerprint: Hex64
    requires_review: bool
    reason_codes: list[Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,127}$")]] = (
        Field(max_length=128)
    )
    decision_id: ShortText | None
    disposition: ReviewDisposition | None
    reviewed_at_ms: EpochMilliseconds | None
    reviewed_by: ShortText | None
    rationale: BoundedText | None

    @field_validator("decision_id", "reviewed_by", "rationale")
    @classmethod
    def reject_optional_control_characters(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_bounded_text(value, "review")
        return value

    @model_validator(mode="after")
    def validate_review_binding(self) -> Self:
        decision_fields = (
            self.decision_id,
            self.disposition,
            self.reviewed_at_ms,
        )
        attribution_fields = (self.reviewed_by, self.rationale)
        if self.requires_review:
            if any(value is None for value in decision_fields):
                raise ValueError("required review decision is incomplete")
            if any(value is None for value in attribution_fields):
                raise ValueError("required review attribution is incomplete")
            if not self.reason_codes:
                raise ValueError("required review must include reason_codes")
            if self.disposition != "approved":
                raise ValueError("required review must be approved before cloud copy")
        else:
            if any(
                value is not None for value in (*decision_fields, *attribution_fields)
            ):
                raise ValueError("non-review lineage cannot contain a review decision")
            if self.reason_codes:
                raise ValueError("non-review lineage cannot contain review reasons")
        return self


class FileCloudCopyLineage(StrictLineageModel):
    receipt_id: Hex64
    lineage_fingerprint: Hex64
    provider: Literal["icloud", "onedrive", "google-drive"]
    destination_account_scope: Literal["personal", "organization", "shared", "unknown"]
    destination: BoundedText
    copied_at_ms: EpochMilliseconds
    copy_verification_method: Literal["copied-by-disk-sage", "adopted-existing"]
    local_copy_verified: Literal[True]
    provider_write_executed: Literal[False]
    provider_sync_confirmed: bool
    sync_evidence_record_id: Hex64 | None
    sync_evidence_kind: Literal["provider-api", "provider-native-status"] | None
    sync_evidence_id: ShortText | None
    sync_confirmed_at_ms: EpochMilliseconds | None
    remote_object_id: ShortText | None
    remote_revision: ShortText | None
    remote_location_bound: bool | None

    @field_validator(
        "destination",
        "sync_evidence_id",
        "remote_object_id",
        "remote_revision",
    )
    @classmethod
    def reject_optional_control_characters(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_bounded_text(value, "cloud_copy")
        return value

    @model_validator(mode="after")
    def validate_sync_evidence_binding(self) -> Self:
        required_sync_fields = (
            self.sync_evidence_record_id,
            self.sync_evidence_kind,
            self.sync_evidence_id,
            self.sync_confirmed_at_ms,
        )
        remote_fields = (
            self.remote_object_id,
            self.remote_revision,
            self.remote_location_bound,
        )
        evidence_present = any(value is not None for value in required_sync_fields)
        if evidence_present and any(value is None for value in required_sync_fields):
            raise ValueError("provider sync evidence is incomplete")
        if self.provider_sync_confirmed and not evidence_present:
            raise ValueError("confirmed provider sync evidence is missing")
        if evidence_present:
            if self.sync_evidence_kind == "provider-api":
                if any(value is None for value in remote_fields):
                    raise ValueError("provider API evidence must bind remote content")
            elif any(value is not None for value in remote_fields):
                raise ValueError("provider native evidence cannot claim remote content")
        elif any(value is not None for value in remote_fields):
            raise ValueError("remote content cannot exist without sync evidence")
        return self


class DiskSageFileLineageEnvelope(StrictLineageModel):
    schema_version: Literal[1]
    schema_kind: Literal["disksage.file-lineage"]
    source_kind: Literal["file"]
    archive_kind: Literal[
        "document",
        "media",
        "archive",
        "dataset",
        "backup",
        "creative",
        "incomplete-download",
    ]
    source_filename: ShortText
    source_relative_path: BoundedText
    source_context: BoundedText
    raw_content_sha256: Hex64
    raw_content_blake3: Hex64
    bytes: NonNegativeBytes
    production_time: FileProductionTimeLineage
    filesystem_time: FileFilesystemTimeLineage
    metadata_evidence: list[MetadataEvidence] = Field(max_length=128)
    content_title: BoundedText | None
    content_authors: list[ShortText] = Field(max_length=128)
    content_context: list[BoundedText] = Field(max_length=256)
    duration_ms: EpochMilliseconds | None
    review: FileReviewLineage
    cloud_copy: FileCloudCopyLineage

    @field_validator("source_filename", "source_context", "content_title")
    @classmethod
    def reject_optional_control_characters(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_bounded_text(value, "file_lineage")
        return value

    @field_validator("content_authors", "content_context")
    @classmethod
    def reject_list_control_characters(cls, values: list[str]) -> list[str]:
        for value in values:
            _validate_bounded_text(value, "file_lineage")
        return values

    @model_validator(mode="after")
    def validate_source_path_binding(self) -> Self:
        parts = _relative_path_parts(self.source_relative_path)
        if "/" in self.source_filename or "\\" in self.source_filename:
            raise ValueError("source_filename must be a basename")
        if self.source_filename != parts[-1]:
            raise ValueError("source_filename does not match source_relative_path")
        return self


class FileLineageValidationResponse(StrictLineageModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    schema_version: Literal[1]
    schema_kind: Literal["disksage.file-lineage"]


def validation_response(
    envelope: DiskSageFileLineageEnvelope,
) -> FileLineageValidationResponse:
    """Return only the structural scope and version accepted by Naruon."""

    return FileLineageValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        schema_version=envelope.schema_version,
        schema_kind=envelope.schema_kind,
    )
