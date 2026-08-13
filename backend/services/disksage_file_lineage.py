"""Strict, scope-neutral validation for DiskSage file-lineage envelopes.

DiskSage performs the filesystem and provider proof work locally. Naruon only
accepts the resulting immutable envelope; it never treats a local File
Provider copy as a provider API write or as permission to evict the source.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HEX64_PATTERN = r"^[0-9a-fA-F]{64}$"
ONTOLOGY_CLASS_PATTERN = (
    r"^https://disksage\.app/ontology#[A-Za-z][A-Za-z0-9_-]{0,127}$"
)
PROVIDER_VALUES = Literal["icloud", "onedrive", "google-drive"]
ARCHIVE_KIND_VALUES = Literal[
    "document",
    "media",
    "archive",
    "dataset",
    "backup",
    "creative",
    "incomplete-download",
]
REVIEW_DISPOSITION_VALUES = Literal["approved", "held"]
SYNC_KIND_VALUES = Literal["provider-api", "provider-native-status"]
PROVIDER_SYNC_STATE_VALUES = Literal[
    "complete",
    "pending-upload",
    "not-ubiquitous",
    "not-local-current",
    "uploading",
    "excluded-from-sync",
    "sync-paused",
    "remote-unavailable",
    "content-mismatch",
    "unknown",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FileLineageRelation(_StrictModel):
    subject: str = Field(min_length=1, max_length=2048)
    predicate: str = Field(min_length=1, max_length=256)
    object: str = Field(min_length=1, max_length=2048)
    source: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def reject_control_values(self) -> FileLineageRelation:
        if any(
            any(ord(character) < 32 for character in value)
            for value in (self.subject, self.predicate, self.object, self.source)
        ):
            raise ValueError("lineage relation contains a control character")
        return self


class FileMetadataEvidence(_StrictModel):
    field: str = Field(min_length=1, max_length=128)
    value: str = Field(max_length=2048)
    source: str = Field(min_length=1, max_length=256)
    confidence: Literal["high", "medium", "low", "unknown"]


class ProductionTimeLineage(_StrictModel):
    selected_value_ms: int = Field(ge=0)
    selected_source: str = Field(min_length=1, max_length=256)
    confidence: Literal["high", "medium", "low", "unknown"]
    evidence_precedence: list[str] = Field(min_length=1, max_length=8)


class FilesystemTimeLineage(_StrictModel):
    created_at_ms: int = Field(ge=0)
    modified_at_ms: int = Field(ge=0)


class ReviewLineage(_StrictModel):
    candidate_fingerprint: str = Field(pattern=HEX64_PATTERN)
    review_fingerprint: str = Field(pattern=HEX64_PATTERN)
    requires_review: bool
    reason_codes: list[str] = Field(max_length=64)
    decision_id: str | None = Field(default=None, max_length=256)
    disposition: REVIEW_DISPOSITION_VALUES | None = None
    reviewed_at_ms: int | None = Field(default=None, ge=0)
    reviewed_by: str | None = Field(default=None, max_length=256)
    rationale: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def bind_decision_fields(self) -> ReviewLineage:
        if self.disposition is not None and (
            self.decision_id is None
            or self.reviewed_at_ms is None
            or not self.reviewed_by
            or not self.rationale
        ):
            raise ValueError("review disposition is missing its decision evidence")
        return self


class RemoteContentProof(_StrictModel):
    object_id: str = Field(min_length=1, max_length=512)
    revision: str = Field(min_length=1, max_length=512)
    algorithm: Literal["sha256", "quick-xor"]
    checksum: str = Field(min_length=1, max_length=256)
    location_bound: bool
    location_proof: str | None = Field(default=None, max_length=2048)


class CloudCopyLineage(_StrictModel):
    receipt_id: str = Field(pattern=HEX64_PATTERN)
    lineage_fingerprint: str = Field(pattern=HEX64_PATTERN)
    provider: PROVIDER_VALUES
    destination_account_scope: Literal["personal", "organization", "shared", "unknown"]
    destination: str = Field(min_length=1, max_length=4096)
    copied_at_ms: int = Field(ge=0)
    copy_verification_method: Literal["copied-by-disk-sage", "adopted-existing"]
    local_copy_verified: bool
    provider_write_executed: bool
    provider_sync_confirmed: bool
    # Optional keeps version-1 envelopes backwards compatible; new DiskSage
    # exports preserve provider-native states such as pending-upload.
    provider_sync_state: PROVIDER_SYNC_STATE_VALUES | None = None
    sync_evidence_record_id: str | None = Field(default=None, max_length=256)
    sync_evidence_kind: SYNC_KIND_VALUES | None = None
    sync_evidence_id: str | None = Field(default=None, max_length=512)
    sync_confirmed_at_ms: int | None = Field(default=None, ge=0)
    remote_object_id: str | None = Field(default=None, max_length=512)
    remote_revision: str | None = Field(default=None, max_length=512)
    remote_location_bound: bool | None = None

    @model_validator(mode="after")
    def bind_provider_evidence(self) -> CloudCopyLineage:
        if not self.local_copy_verified:
            raise ValueError("lineage copy is not locally verified")
        if self.provider_write_executed:
            raise ValueError("Naruon cannot accept a provider-write claim")
        evidence_fields = (
            self.sync_evidence_record_id,
            self.sync_evidence_kind,
            self.sync_evidence_id,
            self.sync_confirmed_at_ms,
        )
        if self.provider_sync_confirmed and any(
            value is None for value in evidence_fields
        ):
            raise ValueError("confirmed sync is missing provider evidence")
        if self.provider_sync_state not in (None, "unknown") and (
            self.provider_sync_confirmed != (self.provider_sync_state == "complete")
        ):
            raise ValueError("provider sync state does not match confirmation")
        if self.remote_location_bound is True and not self.remote_object_id:
            raise ValueError("remote location binding is missing its object id")
        return self


class FileLineageEnvelope(_StrictModel):
    # DiskSage v2 adds attributed copy-approval evidence while retaining the
    # v1 ontology envelope shape.
    schema_version: Literal[1, 2]
    schema_kind: Literal["disksage.file-lineage"]
    source_kind: Literal["file"]
    archive_kind: ARCHIVE_KIND_VALUES
    source_filename: str = Field(min_length=1, max_length=512)
    source_relative_path: str = Field(min_length=1, max_length=4096)
    source_context: str = Field(min_length=1, max_length=1024)
    ontology_class: str = Field(pattern=ONTOLOGY_CLASS_PATTERN)
    ontology_relations: list[FileLineageRelation] = Field(max_length=256)
    raw_content_sha256: str = Field(pattern=HEX64_PATTERN)
    raw_content_blake3: str = Field(pattern=HEX64_PATTERN)
    bytes: int = Field(ge=0)
    production_time: ProductionTimeLineage
    filesystem_time: FilesystemTimeLineage
    metadata_evidence: list[FileMetadataEvidence] = Field(max_length=128)
    content_title: str | None = Field(default=None, max_length=1024)
    content_authors: list[str] = Field(max_length=32)
    content_context: list[str] = Field(max_length=64)
    duration_ms: int | None = Field(default=None, ge=0)
    review: ReviewLineage
    cloud_copy: CloudCopyLineage

    @model_validator(mode="after")
    def validate_path_and_relations(self) -> FileLineageEnvelope:
        relative = self.source_relative_path.replace("\\", "/")
        parts = relative.split("/")
        if relative.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("source relative path is not a normalized relative path")
        if self.source_filename != parts[-1]:
            raise ValueError("source filename does not match source relative path")
        if any(ord(character) < 32 for character in relative):
            raise ValueError("source relative path contains a control character")
        return self


class FileLineageSummary(_StrictModel):
    lineage_record_uid: str
    lineage_fingerprint: str
    schema_version: int
    source_kind: str
    archive_kind: str
    raw_content_sha256: str
    raw_content_blake3: str
    bytes: int
    ontology_class: str
    ontology_relation_count: int
    ontology_predicates: list[str]
    provider: PROVIDER_VALUES
    provider_sync_confirmed: bool
    provider_sync_state: PROVIDER_SYNC_STATE_VALUES
    created_at: str


def canonical_envelope_sha256(envelope: FileLineageEnvelope) -> str:
    """Hash the exact validated JSON payload for idempotent, tamper-evident ingest."""

    encoded = json.dumps(
        envelope.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ontology_predicates(envelope: FileLineageEnvelope) -> list[str]:
    """Return a deterministic public projection without path/object values."""

    return sorted({relation.predicate for relation in envelope.ontology_relations})
