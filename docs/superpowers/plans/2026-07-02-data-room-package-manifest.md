# Data Room Package Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a data-room package manifest to the redacted evidence snapshot so a buyer can see the safe file names and evidence artifacts required for diligence handoff.

**Architecture:** Keep the manifest as a derived field on the existing `DataEvidenceSnapshotResponse`. It is generated from already-redacted snapshot fields, included in the tamper-evident digest, and rendered inside the existing `실사 스냅샷` card.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, existing DataLayout styles.

## Global Constraints

- Do not use Figma Code Connect.
- Do not introduce a new library, package split, or git submodule in this phase.
- Keep all manifest entries read-only with `provider_write_executed: false`.
- Do not expose raw email body, raw HTML, attachment bytes, stable provider IDs, database IDs, credentials, or database evidence column strings.
- Preserve unrelated dirty files: `.Jules/palette.md` and `.Jules/sentinel.md`.
- Treat queued review/check workflow state as non-blocking. Failed local validation or failed live checks are actionable.

---

### Task 1: Backend Manifest Contract

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `DataRoomPackageManifestEntry` with fields `manifest_key`, `file_name`, `artifact_type`, `display_name`, `state_code`, `source_field`, `required_for_close`, `contains_raw_content`, `contains_stable_identifiers`, `detail_text`, `provider_write_executed`.
- Produces: `data_room_package_manifest: list[DataRoomPackageManifestEntry]` on `DataEvidenceSnapshotResponse`.

- [ ] **Step 1: Add backend expected fixture**

Add `_expected_data_room_package_manifest()` to `backend/tests/test_data_api.py` with ten entries:

```python
[
    ("evidence_snapshot_json", "naruon-evidence-snapshot.json", "snapshot_json", "Evidence snapshot JSON", "ready", "snapshot_version,snapshot_digest,canonical_payload_fields", True),
    ("offline_verifier", "verify-evidence-snapshot.py", "verifier_script", "Offline digest verifier", "ready", "verification_handoff", True),
    ("privacy_policy", "privacy-redaction-policy.json", "policy_json", "Privacy redaction policy", "ready", "privacy_redaction_policy", True),
    ("attachment_parser_manifest", "attachment-parser-manifest.json", "manifest_json", "Attachment parser manifest", "ready", "parser_manifest_summary", True),
    ("dom_paragraph_samples", "dom-paragraph-evidence-samples.json", "evidence_samples_json", "DOM paragraph evidence samples", "ready", "content_graph_evidence_samples", True),
    ("knowledge_graph_samples", "knowledge-graph-evidence-samples.json", "evidence_samples_json", "Knowledge graph evidence samples", "ready", "knowledge_graph_evidence_samples", True),
    ("semantic_relation_samples", "semantic-relation-evidence-samples.json", "evidence_samples_json", "Semantic relation evidence samples", "ready", "semantic_relation_evidence_samples", True),
    ("evidence_packet_checklist", "buyer-evidence-packet-checklist.json", "manifest_json", "Buyer evidence packet checklist", "needs_attention", "evidence_packet_checklist", True),
    ("acquisition_readiness_summary", "acquisition-readiness-summary.json", "readiness_summary_json", "Acquisition readiness summary", "needs_attention", "acquisition_readiness_gate", True),
    ("remediation_actions", "remediation-actions.json", "readiness_summary_json", "Remediation actions", "needs_attention", "acquisition_readiness_gate.remediation_actions", True),
]
```

All entries must assert `contains_raw_content is False`, `contains_stable_identifiers is False`, and `provider_write_executed is False`.

- [ ] **Step 2: Add Pydantic model and helper**

In `backend/api/data.py`, add `DataRoomManifestState`, `DataRoomArtifactType`, `DataRoomPackageManifestEntry`, and `_data_room_package_manifest(snapshot)`.

- [ ] **Step 3: Include manifest in digest**

Populate `data_room_package_manifest` before `_snapshot_digest_payload(snapshot)` so `canonical_payload_fields` includes `data_room_package_manifest`.

- [ ] **Step 4: Run backend validation**

Run:

```bash
cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface tests/test_evidence_snapshot_verifier.py
cd backend && python -m ruff check api/data.py tests/test_data_api.py scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py
```

- [ ] **Step 5: Commit backend implementation**

Run:

```bash
git add backend/api/data.py backend/tests/test_data_api.py
git commit -m "feat: add data room package manifest"
```

### Task 2: Frontend Manifest Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Test: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.data_room_package_manifest`.
- Produces: an existing-style section titled `Data room package manifest` inside the `실사 스냅샷` card.

- [ ] **Step 1: Add TypeScript type and fixture**

Add `data_room_package_manifest` to `DataEvidenceSnapshotResponse` and mirror the backend fixture in `frontend/src/app/data/page.test.tsx`.

- [ ] **Step 2: Render manifest entries**

Render each entry with file name, artifact type, source field, close-required label, privacy flags, state badge, and write boundary. Use existing card, typography, status, and safe text helpers.

- [ ] **Step 3: Assert UI and copied JSON**

Assert the UI contains `Data room package manifest`, `naruon-evidence-snapshot.json`, `verify-evidence-snapshot.py`, `knowledge-graph-evidence-samples.json`, `acquisition-readiness-summary.json`, and `raw content: no`. Assert copied JSON has ten entries and the readiness summary entry is `needs_attention`.

- [ ] **Step 4: Run frontend validation**

Run:

```bash
cd frontend && npx vitest run src/app/data/page.test.tsx
git diff --check
```

- [ ] **Step 5: Commit frontend implementation**

Run:

```bash
git add frontend/src/components/data-layout/types.ts frontend/src/components/data-layout/QualityCheckTab.tsx frontend/src/app/data/page.test.tsx
git commit -m "feat: show data room package manifest"
```

### Task 3: FigJam, Plan Completion, PR Update

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-data-room-package-manifest.md`

- [ ] **Step 1: Generate FigJam flowchart**

Create a FigJam flowchart showing snapshot -> manifest -> safe data-room files -> verifier -> buyer diligence review.

- [ ] **Step 2: Run Ponytail diff review**

Review the diff for avoidable complexity. Expected acceptable result: no new dependency, no submodule, no speculative abstraction.

- [ ] **Step 3: Mark plan complete and commit**

Update all checkboxes to `[x]`, add execution evidence, and commit:

```bash
git add docs/superpowers/plans/2026-07-02-data-room-package-manifest.md
git commit -m "docs: mark phase 22 plan complete"
```

- [ ] **Step 4: Push, update PR, verify live state**

Push to `plan/email-dom-paragraph-kg-2026-07-02`, append Phase 22 evidence to PR #895, and verify live `headRefOid`, checks, merge state, and unresolved review thread count.
