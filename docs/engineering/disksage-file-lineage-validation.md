# DiskSage file-lineage structural validation

Naruon accepts the bounded `disksage.file-lineage` version 1 envelope at the
authenticated `POST /api/file-lineage/validate` endpoint. This is a general-file
contract and remains separate from the RFC 822-only `EmailSourceLineage` model.
The endpoint neither writes to a provider nor persists the submitted envelope.

## Trust boundary

The response deliberately reports
`validation_scope: schema-and-claim-consistency-only`. A signed Naruon session
authenticates the caller, but the envelope does not contain the original
immutable receipt fields or a detached signature that would let Naruon
recompute and authenticate `receipt_id` or `lineage_fingerprint`. Acceptance
therefore does not mean integrity verified, provider write verified, trusted, or
safe to delete the local source.

The response includes only the accepted schema kind and version. It does not
reflect source or destination paths, content hashes, decision identifiers,
reviewer details, provider evidence identifiers, or provider-capacity evidence.

## Provider-capacity planning evidence

DiskSage can obtain a read-only account-capacity snapshot before a new OneDrive
or Google Drive copy, while iCloud account quota remains unavailable through the
third-party File Provider surface. That snapshot answers whether a proposed
upload is likely to fit at a particular observation time. Naruon does not call
the provider API or revalidate snapshot freshness or account binding. A capacity
gate pass does not identify the copied remote object, prove that the provider
accepted the bytes, attest sync completion, or authorize removal of the local
source.

Capacity is plan-level account evidence rather than file provenance, so it is
not part of the `disksage.file-lineage` version 1 envelope. The strict Naruon
validator rejects a submitted top-level `capacity` field instead of silently
storing account quota as customer file metadata. Provider sync confirmation
continues to require the separate per-file evidence fields already defined by
`cloud_copy`.

If Naruon later needs capacity evidence, it should be introduced as a separate,
versioned `disksage.cloud-capacity-assessment` contract with independent
freshness, provider-account binding, and disclosure review rather than being
added to file lineage.

## Archive content-inclusion relation

DiskSage archive comparison is also kept outside the per-file lineage envelope.
The authenticated `POST /api/archive-content-inclusion/validate` endpoint accepts
the version 1 `disksage.archive-content-inclusion` report produced by DiskSage's
bounded Rust ZIP reader. It verifies strict field shape and internal relations:

- subset and superset archive identifiers are distinct and never reflected;
- subset and superset file counts reconcile with matching, missing, changed,
  and additional counts;
- inclusion and identity booleans are exactly implied by those counts;
- bounded difference-path samples are unique, sorted, portable, category
  disjoint, and consistent with the explicit truncation flag;
- root prefixes agree with the chosen keep/strip mode; and
- lowercase manifest and comparison SHA-256 fields have the expected shape, and
  `comparison_fingerprint_sha256` equals the v1 digest recomputed from
  `root_mode` and the submitted manifest digests.

Naruon does not have either ZIP, so acceptance does not recompute a manifest,
authenticate the producer (the fingerprint is unkeyed and derivable from the
submitted fields), select a canonical archive, or
authorize Trash or cloud-source eviction. The response is redacted and reports
the same `schema-and-claim-consistency-only` scope. This version is database-free
and is intentionally not an ontology, semantic-catalog, or LLM judgment.

## Deterministic checks

The endpoint caps the raw JSON body at 256 KiB before Pydantic parsing and
rejects duplicate object keys, non-finite numbers, excessive nesting, and
unknown fields at every nesting level. Version 1 requires:

- the exact metadata-first production-time order: embedded metadata, explicit
  filename date, filesystem creation time, then filesystem modification time;
- the selected production-time source and confidence to bind matching metadata
  evidence, or the selected filesystem value to equal the claimed creation or
  modification timestamp;
- lowercase 64-character SHA-256, BLAKE3, receipt, review, and lineage digests;
- a cross-platform portable relative source path whose basename equals
  `source_filename` and contains no Windows-reserved component;
- a complete approved human review when `requires_review` is true, with the
  review timestamp no later than the copy timestamp;
- a locally verified copy and `provider_write_executed: false`;
- internally complete provider evidence, while allowing a persisted evidence
  observation whose `provider_sync_confirmed` result remains false, provided that the
  observation does not predate the copy; and
- optional provider-sync timeliness diagnostics whose pending age is bound to
  the copy and observation timestamps, whose fixed 24-hour threshold separates
  `pending` from `overdue`, and whose state can never contradict sync completion;
  legacy version 1 envelopes may omit this diagnostic block; and
- provider API evidence with a true remote-location binding, or provider-native
  evidence without an invented remote object identity.

Malformed envelopes return `disksage_file_lineage_invalid` with HTTP 422.
Oversized bodies return `disksage_file_lineage_too_large` with HTTP 413.

## Persistence and future integrity verification

Version 1 is intentionally database-free, so no Alembic migration,
pg-erd-cloud verification, semantic catalog, ontology, LLM, Noema, or external
orchestrator is needed. If Naruon later uses file lineage as authority for
persistence, automation, or local-source eviction, the producer contract must
first add a detached signature or the complete receipt and provider-evidence
material needed for independent digest recomputation.
