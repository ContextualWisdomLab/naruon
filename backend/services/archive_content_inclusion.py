"""Strict claim-consistency validation for DiskSage archive inclusion evidence."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


U64_MAX = 18_446_744_073_709_551_615
MAX_ARCHIVE_FILES = 100_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024
MAX_PATH_SAMPLES = 1_000
WINDOWS_INVALID_COMPONENT_CHARACTERS = frozenset('<>:"|?*')
WINDOWS_RESERVED_COMPONENT_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"COM{index}" for index in "¹²³"}
    | {f"LPT{index}" for index in "¹²³"}
)

Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
BoundedText = Annotated[str, Field(min_length=1, max_length=4096)]
FileCount = Annotated[int, Field(ge=0, le=MAX_ARCHIVE_FILES)]
PositiveFileCount = Annotated[int, Field(ge=1, le=MAX_ARCHIVE_FILES)]
UncompressedBytes = Annotated[
    int,
    Field(ge=0, le=min(U64_MAX, MAX_ARCHIVE_UNCOMPRESSED_BYTES)),
]


def _validate_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{field_name} contains a control character")
    return value


def _logical_path_parts(value: str) -> tuple[str, ...]:
    _validate_text(value, "logical_path")
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise ValueError("logical_path must be relative")
    if "\\" in value:
        raise ValueError("logical_path must use forward slashes")
    parts = tuple(value.split("/"))
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("logical_path contains an unsafe component")
    for part in parts:
        if part.endswith((" ", ".")):
            raise ValueError("logical_path contains a non-portable component")
        if any(character in WINDOWS_INVALID_COMPONENT_CHARACTERS for character in part):
            raise ValueError("logical_path contains a non-portable component")
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED_COMPONENT_NAMES:
            raise ValueError("logical_path contains a reserved component")
    return parts


def _canonical_archive_identity(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\\", "/")).casefold()


def _comparison_fingerprint_sha256(
    root_mode: str,
    subset_manifest_sha256: str,
    superset_manifest_sha256: str,
) -> str:
    root_mode_bytes = root_mode.encode("utf-8")
    hasher = hashlib.sha256()
    hasher.update(b"disksage.archive-content-inclusion\0v1\0")
    hasher.update(len(root_mode_bytes).to_bytes(8, byteorder="little"))
    hasher.update(root_mode_bytes)
    hasher.update(b"subset\0")
    hasher.update(bytes.fromhex(subset_manifest_sha256))
    hasher.update(b"superset\0")
    hasher.update(bytes.fromhex(superset_manifest_sha256))
    return hasher.hexdigest()


class StrictArchiveEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DiskSageArchiveContentInclusionEnvelope(StrictArchiveEvidenceModel):
    version: Literal[1]
    schema_kind: Literal["disksage.archive-content-inclusion"]
    subset_archive: BoundedText
    superset_archive: BoundedText
    root_mode: Literal["keep-top-level", "strip-shared-root"]
    subset_root_prefix: BoundedText
    superset_root_prefix: BoundedText
    subset_file_count: PositiveFileCount
    superset_file_count: PositiveFileCount
    subset_uncompressed_bytes: UncompressedBytes
    superset_uncompressed_bytes: UncompressedBytes
    matching_file_count: FileCount
    missing_file_count: FileCount
    changed_file_count: FileCount
    additional_file_count: FileCount
    subset_content_included: bool
    archives_identical: bool
    missing_paths: list[BoundedText] = Field(max_length=MAX_PATH_SAMPLES)
    changed_paths: list[BoundedText] = Field(max_length=MAX_PATH_SAMPLES)
    additional_paths: list[BoundedText] = Field(max_length=MAX_PATH_SAMPLES)
    paths_truncated: bool
    subset_manifest_sha256: Hex64
    superset_manifest_sha256: Hex64
    comparison_fingerprint_sha256: Hex64

    @field_validator("version", mode="before")
    @classmethod
    def validate_exact_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("version must be integer 1")
        return value

    @field_validator("subset_archive", "superset_archive")
    @classmethod
    def validate_archive_identifiers(cls, value: str) -> str:
        return _validate_text(value, "archive")

    @field_validator("subset_root_prefix", "superset_root_prefix")
    @classmethod
    def validate_root_prefixes(cls, value: str) -> str:
        _validate_text(value, "root_prefix")
        if value != "." and ("/" in value or "\\" in value or value in {"", ".."}):
            raise ValueError("root_prefix must be one path component")
        return value

    @field_validator("missing_paths", "changed_paths", "additional_paths")
    @classmethod
    def validate_path_samples(cls, values: list[str]) -> list[str]:
        for value in values:
            _logical_path_parts(value)
        if values != sorted(values) or len(values) != len(set(values)):
            raise ValueError("path samples must be unique and sorted")
        return values

    @model_validator(mode="after")
    def validate_claim_bindings(self) -> Self:
        if _canonical_archive_identity(
            self.subset_archive
        ) == _canonical_archive_identity(self.superset_archive):
            raise ValueError("subset and superset archives must be distinct")

        if self.root_mode == "keep-top-level":
            if self.subset_root_prefix != "." or self.superset_root_prefix != ".":
                raise ValueError("keep-top-level requires dot root prefixes")
        elif self.subset_root_prefix == "." or self.superset_root_prefix == ".":
            raise ValueError("stripped roots require explicit wrapper prefixes")

        if self.subset_file_count != (
            self.matching_file_count + self.missing_file_count + self.changed_file_count
        ):
            raise ValueError("subset file count is inconsistent")
        if self.superset_file_count != (
            self.matching_file_count
            + self.changed_file_count
            + self.additional_file_count
        ):
            raise ValueError("superset file count is inconsistent")

        expected_included = (
            self.missing_file_count == 0 and self.changed_file_count == 0
        )
        if self.subset_content_included != expected_included:
            raise ValueError("subset inclusion flag is inconsistent")
        expected_identical = expected_included and self.additional_file_count == 0
        if self.archives_identical != expected_identical:
            raise ValueError("archive identity flag is inconsistent")

        samples_and_counts = (
            (self.missing_paths, self.missing_file_count),
            (self.changed_paths, self.changed_file_count),
            (self.additional_paths, self.additional_file_count),
        )
        if any(len(samples) > count for samples, count in samples_and_counts):
            raise ValueError("path sample count exceeds the reported difference count")
        expected_truncated = any(
            len(samples) < count for samples, count in samples_and_counts
        )
        if self.paths_truncated != expected_truncated:
            raise ValueError("path truncation flag is inconsistent")

        category_paths = [
            path for samples, _count in samples_and_counts for path in samples
        ]
        if len(category_paths) != len(set(category_paths)):
            raise ValueError("path samples overlap difference categories")

        if (
            self.subset_content_included
            and self.superset_uncompressed_bytes < self.subset_uncompressed_bytes
        ):
            raise ValueError("included superset cannot have fewer content bytes")
        manifests_identical = (
            self.subset_manifest_sha256 == self.superset_manifest_sha256
        )
        if self.archives_identical != manifests_identical:
            raise ValueError("archive identity flag does not match manifest identity")
        if self.archives_identical and (
            self.subset_uncompressed_bytes != self.superset_uncompressed_bytes
        ):
            raise ValueError("identical archives require identical byte totals")
        expected_fingerprint = _comparison_fingerprint_sha256(
            self.root_mode,
            self.subset_manifest_sha256,
            self.superset_manifest_sha256,
        )
        if not hmac.compare_digest(
            self.comparison_fingerprint_sha256,
            expected_fingerprint,
        ):
            raise ValueError("comparison fingerprint does not bind submitted manifests")
        return self


class ArchiveContentInclusionValidationResponse(StrictArchiveEvidenceModel):
    valid: Literal[True]
    validation_scope: Literal["schema-and-claim-consistency-only"]
    schema_version: Literal[1]
    schema_kind: Literal["disksage.archive-content-inclusion"]


def archive_content_inclusion_validation_response(
    envelope: DiskSageArchiveContentInclusionEnvelope,
) -> ArchiveContentInclusionValidationResponse:
    """Return no submitted archive, path, count, or digest material."""

    return ArchiveContentInclusionValidationResponse(
        valid=True,
        validation_scope="schema-and-claim-consistency-only",
        schema_version=envelope.version,
        schema_kind=envelope.schema_kind,
    )
