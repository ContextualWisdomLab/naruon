"""Strict validation for DiskSage's path-free local organization handoff."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HEX64_PATTERN = r"^[0-9a-f]{64}$"
ONTOLOGY_CLASS_PATTERN = (
    r"^https://disksage\.app/ontology#[A-Za-z][A-Za-z0-9_-]{0,127}$"
)
PRODUCTION_SOURCES = (
    "embedded:",
    "filename:path-token",
    "filesystem:created",
    "filesystem:modified-fallback",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationLineageItem(_StrictModel):
    lineage_fingerprint: str = Field(pattern=HEX64_PATTERN)
    source_size: int = Field(ge=0)
    source_mtime_ms: int = Field(ge=0)
    production_time_ms: int = Field(gt=0)
    production_time_source: str = Field(min_length=1, max_length=256)
    production_time_confidence: Literal["high", "medium", "low", "unknown"]
    ontology_class: str = Field(pattern=ONTOLOGY_CLASS_PATTERN)
    destination_relation: Literal["targetFolder"]
    action: Literal["move"]

    @model_validator(mode="after")
    def validate_production_source(self) -> OrganizationLineageItem:
        if not any(
            self.production_time_source == source
            or self.production_time_source.startswith(source)
            for source in PRODUCTION_SOURCES
        ):
            raise ValueError("organization lineage production source is unsupported")
        if not self.production_time_source.isprintable():
            raise ValueError("organization lineage production source contains control characters")
        return self


class OrganizationLineageBatch(_StrictModel):
    schema_kind: Literal["disksage.organization-lineage-batch"] = Field(alias="schema")
    version: Literal[1]
    generated_at_ms: int = Field(gt=0)
    complete: Literal[True]
    batch_fingerprint_sha256: str = Field(pattern=HEX64_PATTERN)
    items: list[OrganizationLineageItem] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_batch(self) -> OrganizationLineageBatch:
        fingerprints = [item.lineage_fingerprint for item in self.items]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("organization lineage fingerprints must be unique")
        if self.generated_at_ms > 253_402_300_799_999:
            raise ValueError("organization lineage generated time is out of bounds")
        return self


class OrganizationLineageSummary(_StrictModel):
    organization_lineage_record_uid: str
    batch_fingerprint_sha256: str
    schema_version: int
    item_count: int
    ontology_classes: list[str]
    created_at: str


def canonical_batch_json(batch: OrganizationLineageBatch) -> str:
    return json.dumps(
        batch.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_batch_sha256(batch: OrganizationLineageBatch) -> str:
    return hashlib.sha256(canonical_batch_json(batch).encode("utf-8")).hexdigest()
