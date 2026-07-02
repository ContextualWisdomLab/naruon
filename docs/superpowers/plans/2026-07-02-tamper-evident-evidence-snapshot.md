# Tamper-Evident Evidence Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic SHA-256 digest to the buyer-facing evidence snapshot so copied due-diligence JSON can be checked for tampering without exposing raw email or attachment content.

**Architecture:** Keep the digest inside the existing `/api/data/quality-surface/evidence-snapshot` response and Data UI snapshot panel. Use Python and browser-native JSON handling only; do not introduce signing infrastructure, a new package, a submodule, a migration, or Figma Code Connect.

**Tech Stack:** Python 3.14 stdlib `json`/`hashlib`, FastAPI/Pydantic, React/TypeScript, pytest, Vitest, ruff, Figma/FigJam.

## Global Constraints

- Preserve unrelated `.Jules/*` worktree changes by staging only Phase 12 files.
- Digest canonical payload must exclude `snapshot_digest`, `digest_algorithm`, and `canonical_payload_fields` to avoid self-reference.
- Digest canonical payload must include only buyer-facing snapshot fields that are already safe to copy.
- Do not expose raw email body, raw HTML, attachment bytes, message IDs, attachment IDs, source record IDs, stable database IDs, provider credentials, DB evidence column strings, or sample raw identifiers.
- Do not add dependencies, migrations, package splits, submodules, key management, HMAC secrets, or public CI mail-corpus flows.
- Review process and queued/pending CI are not blockers; failed CI is actionable.

---

### Task 1: Backend Digest Contract Test

**Files:**
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Expects: `GET /api/data/quality-surface/evidence-snapshot`
- Expects: `snapshot_digest: str`
- Expects: `digest_algorithm: "sha256"`
- Expects: `canonical_payload_fields: list[str]`

- [x] **Step 1: Add digest recomputation assertion**

In `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`, copy the snapshot dict, remove `snapshot_digest`, `digest_algorithm`, and `canonical_payload_fields`, then recompute:

```python
canonical_payload = json.dumps(
    digest_payload,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")
assert snapshot["snapshot_digest"] == hashlib.sha256(canonical_payload).hexdigest()
assert snapshot["digest_algorithm"] == "sha256"
assert snapshot["canonical_payload_fields"] == sorted(digest_payload)
```

- [x] **Step 2: Assert digest shape and non-leakage**

Assert the digest is 64 lowercase hex characters and that `canonical_payload_fields` does not include raw or self-referential fields.

- [x] **Step 3: Verify failure before implementation**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
```

Expected: FAIL because the digest fields do not exist yet.

### Task 2: Backend Digest Implementation

**Files:**
- Modify: `backend/api/data.py`

**Interfaces:**
- Produces: `DataEvidenceSnapshotResponse.snapshot_digest`
- Produces: `DataEvidenceSnapshotResponse.digest_algorithm`
- Produces: `DataEvidenceSnapshotResponse.canonical_payload_fields`

- [x] **Step 1: Import `json`**

Add `import json` beside the existing stdlib imports.

- [x] **Step 2: Add digest fields to response model**

Add fields to `DataEvidenceSnapshotResponse`:

```python
snapshot_digest: str
digest_algorithm: Literal["sha256"]
canonical_payload_fields: list[str]
```

- [x] **Step 3: Add canonical digest helper**

Add:

```python
SNAPSHOT_DIGEST_EXCLUDED_FIELDS = {
    "snapshot_digest",
    "digest_algorithm",
    "canonical_payload_fields",
}


def _snapshot_digest_payload(snapshot: DataEvidenceSnapshotResponse) -> dict[str, object]:
    payload = snapshot.model_dump(mode="json")
    for field_name in SNAPSHOT_DIGEST_EXCLUDED_FIELDS:
        payload.pop(field_name, None)
    return payload


def _snapshot_digest_for(payload: dict[str, object]) -> str:
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()
```

- [x] **Step 4: Populate digest after base response construction**

Build the base snapshot with empty digest metadata, derive the payload, then return a copy with:

```python
return snapshot.model_copy(update={
    "snapshot_digest": _snapshot_digest_for(digest_payload),
    "digest_algorithm": "sha256",
    "canonical_payload_fields": sorted(digest_payload),
})
```

- [x] **Step 5: Verify backend pass**

Run:

```bash
cd backend
python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface
ruff check api/data.py tests/test_data_api.py
```

Expected: PASS.

### Task 3: Frontend Digest Display And Copy Test

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `DataEvidenceSnapshotResponse.snapshot_digest`
- Consumes: `DataEvidenceSnapshotResponse.digest_algorithm`
- Consumes: `DataEvidenceSnapshotResponse.canonical_payload_fields`

- [x] **Step 1: Extend frontend type**

Add the three backend fields to `DataEvidenceSnapshotResponse`.

- [x] **Step 2: Extend test fixture**

Add a stable 64-character hex `snapshot_digest`, `digest_algorithm: "sha256"`, and `canonical_payload_fields` to `dataEvidenceSnapshot`.

- [x] **Step 3: Render digest fingerprint**

In the snapshot panel, add two compact values:

- `Digest`: the first 12 characters of `snapshot_digest`
- `Algorithm`: `digest_algorithm`

Keep the full digest out of visible UI to avoid layout noise, but leave it in copied JSON.

- [x] **Step 4: Assert UI and copy payload**

In the quality tab test, assert the short digest and algorithm are visible, and the copied JSON contains the full digest.

- [x] **Step 5: Verify frontend pass**

Run:

```bash
cd frontend
pnpm test src/app/data/page.test.tsx
pnpm typecheck
```

Expected: PASS.

### Task 4: Figma/FigJam Evidence

**Files:**
- No repo file unless screenshot is intentionally stored outside the repo

- [x] **Step 1: Add Phase 12 diagram**

Use `generate_diagram` on FigJam board `zXkcwT2E2aBtNhMVznLT4l` with a flowchart showing:

- Evidence snapshot payload
- Canonical JSON payload without digest metadata
- SHA-256 digest
- Data UI short fingerprint
- Copied buyer packet with full digest
- Buyer-side recomputation check

- [x] **Step 2: Group and screenshot**

Group the generated nodes as `Phase 12 Tamper-Evident Snapshot Digest Group` and download a screenshot for local visual inspection.

### Task 5: Ship

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-tamper-evident-evidence-snapshot.md`
- Modify: PR body via `gh pr edit`

- [ ] **Step 1: Run final diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 2: Commit implementation**

Stage only Phase 12 files and commit:

```bash
git commit -m "feat: add evidence snapshot digest"
```

- [ ] **Step 3: Push**

Push to `plan/email-dom-paragraph-kg-2026-07-02`.

- [ ] **Step 4: Mark plan complete and commit docs**

Check off completed ship steps, commit:

```bash
git commit -m "docs: mark phase 12 plan complete"
```

- [ ] **Step 5: Update PR body**

Add Phase 12 scope, validation results, FigJam screenshot path, and current head SHA to PR #895.

- [ ] **Step 6: Live PR check**

Re-check PR #895 head, mergeability, checks, and body. Treat queued/pending/review status as non-blocking and failed checks as actionable.
