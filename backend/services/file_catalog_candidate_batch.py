"""Strict, non-persisting validation for DiskSage catalog candidate batches.

The submitted metadata can contain private document metadata. Naruon therefore
validates the bounded wire contract and deterministic production-time claims
without reflecting content, opening a database session, calling an LLM, or
authorizing copy or eviction. Ontology projection remains the responsibility of
semantic-data-portal.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DISKSAGE_FILE_CATALOG_SCHEMA = "disksage.file-catalog-candidate-batch"
DISKSAGE_FILE_CATALOG_VERSION = 1
MAX_DISKSAGE_FILE_CATALOG_CANDIDATES = 200
MAX_DATETIME_EPOCH_MS = 253_402_300_799_999
U64_MAX = 18_446_744_073_709_551_615
PRODUCTION_TIME_PRECEDENCE = [
    "embedded_metadata",
    "explicit_filename_date",
    "filesystem_created",
    "filesystem_modified",
]

U64 = Annotated[int, Field(ge=0, le=U64_MAX)]
EpochMilliseconds = Annotated[int, Field(ge=0, le=MAX_DATETIME_EPOCH_MS)]
PositiveEpochMilliseconds = Annotated[
    int,
    Field(gt=0, le=MAX_DATETIME_EPOCH_MS),
]
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
CloudProvider = Literal["icloud", "onedrive", "google-drive"]
CloudAccountScope = Literal["personal", "organization", "shared", "unknown"]
ArchiveKind = Literal[
    "document",
    "media",
    "archive",
    "dataset",
    "backup",
    "creative",
    "incomplete-download",
]
Confidence = Literal["high", "medium", "low", "unknown"]
ProductionTimeSourceClass = Literal[
    "embedded_metadata",
    "explicit_filename_date",
    "filesystem_created",
    "filesystem_modified",
]


class StrictCatalogModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )


class DiskSageMetadataEvidence(StrictCatalogModel):
    field: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=2048)
    source: str = Field(min_length=1, max_length=256)
    confidence: Confidence


class DiskSageDatasetColumnProfile(StrictCatalogModel):
    name: str = Field(min_length=1, max_length=256)
    inferred_type: str = Field(min_length=1, max_length=64)
    observed_values: U64
    missing_values: U64
    sensitive_name: bool


class DiskSageDatasetProfile(StrictCatalogModel):
    format: str = Field(min_length=1, max_length=64)
    sampled_rows: U64
    sampled_worksheets: U64
    worksheet_names: list[str] = Field(default_factory=list, max_length=128)
    profile_complete: bool
    sample_truncated: bool
    columns: list[DiskSageDatasetColumnProfile] = Field(
        default_factory=list,
        max_length=512,
    )
    quality_warnings: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_nested_text(self) -> Self:
        if any(not value or len(value) > 256 for value in self.worksheet_names):
            raise ValueError("worksheet names are out of bounds")
        if any(not value or len(value) > 256 for value in self.quality_warnings):
            raise ValueError("quality warnings are out of bounds")
        return self


def production_time_source_class(source: str) -> ProductionTimeSourceClass:
    """Map the exact DiskSage source token to the fixed policy class."""

    if source.startswith("embedded:"):
        return "embedded_metadata"
    if source == "filename:path-token":
        return "explicit_filename_date"
    if source == "filesystem:created":
        return "filesystem_created"
    if source == "filesystem:modified-fallback":
        return "filesystem_modified"
    raise ValueError("unsupported production time source")


def _date_value(epoch_ms: int) -> str:
    return (
        (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=epoch_ms))
        .date()
        .isoformat()
    )


def _evidence_source_class(
    evidence: DiskSageMetadataEvidence,
) -> ProductionTimeSourceClass | None:
    if evidence.field == "production-date" and evidence.source.startswith("embedded:"):
        return "embedded_metadata"
    if (
        evidence.field == "filename-date-hint"
        and evidence.source == "filename:path-token"
    ):
        return "explicit_filename_date"
    if (
        evidence.field == "filesystem-created-date"
        and evidence.source == "filesystem:created"
    ):
        return "filesystem_created"
    if (
        evidence.field == "filesystem-modified-date"
        and evidence.source == "filesystem:modified"
    ):
        return "filesystem_modified"
    return None


class DiskSageCatalogCandidate(StrictCatalogModel):
    candidate_fingerprint: Hex64
    review_fingerprint: Hex64
    destination_provider: CloudProvider
    destination_account_scope: CloudAccountScope
    archive_kind: ArchiveKind
    bytes: U64
    created_ms: EpochMilliseconds
    modified_ms: PositiveEpochMilliseconds
    production_time_ms: PositiveEpochMilliseconds
    production_time_source: str = Field(min_length=1, max_length=256)
    production_time_confidence: Confidence
    requires_review: bool
    review_reasons: list[str] = Field(default_factory=list, max_length=128)
    content_title: str | None = Field(default=None, min_length=1, max_length=1024)
    content_authors: list[str] = Field(default_factory=list, max_length=64)
    content_context: list[str] = Field(default_factory=list, max_length=128)
    duration_ms: U64 | None = None
    dataset_profile: DiskSageDatasetProfile | None = None
    metadata_evidence: list[DiskSageMetadataEvidence] = Field(
        default_factory=list,
        max_length=256,
    )
    blocked_reason: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_metadata_lineage(self) -> Self:
        bounded_lists = (
            (self.review_reasons, 256),
            (self.content_authors, 256),
            (self.content_context, 1024),
        )
        for values, max_length in bounded_lists:
            if any(not value or len(value) > max_length for value in values):
                raise ValueError("catalog candidate text is out of bounds")

        source_class = production_time_source_class(self.production_time_source)
        expected_field, expected_source = {
            "embedded_metadata": (
                "production-date",
                self.production_time_source,
            ),
            "explicit_filename_date": (
                "filename-date-hint",
                "filename:path-token",
            ),
            "filesystem_created": (
                "filesystem-created-date",
                "filesystem:created",
            ),
            "filesystem_modified": (
                "filesystem-modified-date",
                "filesystem:modified",
            ),
        }[source_class]
        selected_date = _date_value(self.production_time_ms)
        if not any(
            evidence.field == expected_field
            and evidence.source == expected_source
            and evidence.value == selected_date
            for evidence in self.metadata_evidence
        ):
            raise ValueError(
                "selected production time is not bound to matching evidence"
            )

        selected_rank = PRODUCTION_TIME_PRECEDENCE.index(source_class)
        evidence_classes = {
            evidence_class
            for evidence in self.metadata_evidence
            if (evidence_class := _evidence_source_class(evidence)) is not None
        }
        if any(
            PRODUCTION_TIME_PRECEDENCE.index(evidence_class) < selected_rank
            for evidence_class in evidence_classes
        ):
            raise ValueError("production time violates metadata precedence")
        if (
            source_class != "embedded_metadata"
            and self.production_time_confidence != "low"
        ):
            raise ValueError("non-embedded production time must remain low confidence")
        if self.requires_review != bool(self.review_reasons):
            raise ValueError("review claim is inconsistent")
        return self


class DiskSageCatalogCandidateBatch(StrictCatalogModel):
    schema_kind: Literal["disksage.file-catalog-candidate-batch"] = Field(
        alias="schema"
    )
    version: Literal[1]
    production_time_precedence: list[ProductionTimeSourceClass] = Field(
        min_length=4,
        max_length=4,
    )
    generated_at_ms: PositiveEpochMilliseconds
    candidates: list[DiskSageCatalogCandidate] = Field(
        min_length=1,
        max_length=MAX_DISKSAGE_FILE_CATALOG_CANDIDATES,
    )

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value != DISKSAGE_FILE_CATALOG_VERSION:
            raise ValueError("catalog version must be integer 1")
        return value

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        if self.production_time_precedence != PRODUCTION_TIME_PRECEDENCE:
            raise ValueError("production time precedence is not canonical")
        fingerprints = [
            candidate.candidate_fingerprint for candidate in self.candidates
        ]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("candidate fingerprints must be unique")
        return self


class FileCatalogCandidateBatchValidationResponse(StrictCatalogModel):
    valid: Literal[True]
    validation_scope: Literal["schema-metadata-precedence-and-claim-consistency-only"]
    schema_kind: Literal["disksage.file-catalog-candidate-batch"]
    schema_version: Literal[1]
    candidate_count: Annotated[
        int,
        Field(ge=1, le=MAX_DISKSAGE_FILE_CATALOG_CANDIDATES),
    ]
    private_content_reflected: Literal[False]
    persisted: Literal[False]
    llm_used: Literal[False]
    copy_authorized: Literal[False]
    eviction_authorized: Literal[False]
    persistable_as_file_asset: Literal[False]
    content_sha256_required: Literal[True]
    semantic_projection_delegated_to: Literal["semantic-data-portal"]


def validation_response(
    batch: DiskSageCatalogCandidateBatch,
) -> FileCatalogCandidateBatchValidationResponse:
    """Return only fixed, redacted contract metadata and a bounded count."""

    return FileCatalogCandidateBatchValidationResponse(
        valid=True,
        validation_scope="schema-metadata-precedence-and-claim-consistency-only",
        schema_kind=batch.schema_kind,
        schema_version=batch.version,
        candidate_count=len(batch.candidates),
        private_content_reflected=False,
        persisted=False,
        llm_used=False,
        copy_authorized=False,
        eviction_authorized=False,
        persistable_as_file_asset=False,
        content_sha256_required=True,
        semantic_projection_delegated_to="semantic-data-portal",
    )
