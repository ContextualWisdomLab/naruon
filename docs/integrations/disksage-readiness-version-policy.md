# DiskSage readiness schema compatibility

Naruon delegates validation of DiskSage cloud-copy readiness artifacts to the digest-bound offline Rust verifier and then validates the verifier's bounded JSON response.

## Supported versions

Naruon accepts exactly these successful response versions:

- **Schema 3** — the deployed readiness contract used before WAL-consistency evidence was added.
- **Schema 4** — the WAL-consistent readiness contract.

Supporting version 4 is an additive compatibility change. Version 3 remains valid so an independently deployed DiskSage installation does not fail merely because Naruon upgrades first. Versions outside this explicit set are rejected.

## Invariants shared by both versions

A successful response must retain the exact allowlisted fields, a recognized provider and readiness state, non-negative candidate counts and byte totals, a lowercase SHA-256 fingerprint, and false values for every local-path, raw-metadata, cloud-write, and source-eviction claim. Duplicate JSON member names, unexpected stderr, oversized output, invalid encodings, unknown fields, or unsupported exit codes fail closed.

The compatibility policy changes only the accepted schema-version set. It does not authorize a cloud write, source eviction, network request, or access to local file paths.
