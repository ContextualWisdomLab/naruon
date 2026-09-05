# Tenant Provenance Round-Trip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a signed deterministic export/reimport path preserving the current
workspace's email-derived project evidence and correction history.

**Architecture:** Query the existing SQLAlchemy provenance graph by signed scope,
serialize stable identities into a bounded BagIt/RO-Crate ZIP, validate the full
closure, and restore it transactionally with fresh keys. The existing data router
exposes the operations.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Python standard library,
PostgreSQL/pgvector, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-tenant-provenance-roundtrip-design.md`

## Global Constraints

- Never inspect, copy, commit, or upload `tests/real_datasets`.
- Never serialize credentials, encrypted secrets, embeddings, integer keys,
  binary documents, provider URLs or tokens, or legacy audit details.
- Source scope and target authority come from the signed session.
- Validate the bounded archive and reference graph before mutation.
- Add no dependency. The coexistence-safe implementation adds one internal
  portable-to-database identity mapping table; its multi-word sequential key
  `provenance_identity_id` is never serialized or exposed through the API.
- Treat warning-class output as failure.

---

### Task 1: Deterministic envelope and validator

**Files:** Create `backend/services/tenant_provenance_bundle.py`; create
`backend/tests/test_tenant_provenance_bundle.py`.

**Interfaces:** `build_provenance_archive(records) -> bytes` and
`parse_provenance_archive(archive_bytes) -> dict[str, object]`.

- [ ] Write deterministic-byte and exact-entry tests; run and verify RED.
- [ ] Add RED tests for tampering, unsafe/colliding paths, bounds, missing or
  extra entries, and duplicate JSON keys.
- [ ] Implement fixed ZIP metadata, canonical JSON, SHA-512 manifests, RO-Crate
  metadata, bounded reads, and fail-closed validation with the standard library.
- [ ] Run the focused tests with `PYTHONWARNINGS=error` and require clean output.

### Task 2: Scoped export and transactional reimport

**Files:** Modify the service and focused test from Task 1.

**Interfaces:** `TenantProvenanceScope`, `export_tenant_provenance`,
`import_tenant_provenance`, and `ImportReceipt`.

- [ ] Seed Email through Correction in the PostgreSQL harness; write and run a
  failing clean-target round-trip assertion over UIDs, hashes, and correction JSON.
- [ ] Add RED scope, dangling-reference rollback, conflict, text-admission,
  secret/embedding absence, and idempotency tests.
- [ ] Implement scoped selects, stable records, pre-mutation validation, FK-order
  restore maps, exact duplicate skips, and a single transaction boundary.
- [ ] Run the focused PostgreSQL suite with warnings promoted to errors.

### Task 3: Signed data API

**Files:** Modify `backend/api/data.py` and `backend/tests/test_data_api.py`.

**Interfaces:** `GET /api/data/provenance-bundle` and
`POST /api/data/provenance-bundle/import`.

- [ ] Add RED tests for authentication, response media/disposition, oversize
  input, fixed safe errors, and target-scope rewrite.
- [ ] Add the two signed endpoints using bounded raw ZIP bytes and known errors.
- [ ] Run focused data API and bundle tests with warnings promoted to errors.

### Task 4: Documentation truth and release evidence

**Files:** Modify ADR index, product baseline, platform plan, and CHANGELOG.

- [ ] Index ADR-0022 (formerly ADR-0007), correct the stale test-only graph claim, and retain the full
  portability gap after recording this bounded implemented slice.
- [ ] Run Ruff, focused suites, the full backend suite, and `git diff --check`.
- [ ] Confirm `git ls-files tests/real_datasets` is empty and inspect the complete
  diff before committing and opening a PR.
