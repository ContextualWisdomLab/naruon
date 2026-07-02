# Diligence Risk Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a buyer-facing diligence risk matrix to the redacted evidence snapshot so acquisition reviewers can prioritize remaining close blockers by severity, owner area, and data-room artifact.

**Architecture:** Derive matrix entries from the existing `diligence_exception_register`, not from raw email, attachment, database, or provider data. Keep the matrix inside `DataEvidenceSnapshotResponse`, include it in the tamper-evident digest, and render it inside the existing `실사 스냅샷` card after the exception register.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, existing DataLayout styles.

## Global Constraints

- Do not use Figma Code Connect.
- Do not introduce a new library, package split, or git submodule in this phase.
- Keep all matrix entries read-only with `provider_write_executed: false`.
- Do not expose raw email body, raw HTML, attachment bytes, stable provider IDs, database IDs, credentials, or database evidence column strings.
- Preserve unrelated dirty files: `.Jules/palette.md` and `.Jules/sentinel.md`.
- Treat queued review/check workflow state as non-blocking. Failed local validation or failed live checks are actionable.
- CodeGraph is absent in this worktree, so use focused file reads and `rg` for this phase.

---

### Task 1: Backend Risk Matrix Contract

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `DataDiligenceRiskMatrixEntry` with fields `matrix_key`, `severity_code`, `owner_area`, `related_artifact`, `exception_count`, `representative_exception_keys`, `risk_label`, `buyer_implication`, `recommended_next_action`, `blocks_close`, `provider_write_executed`.
- Produces: `diligence_risk_matrix: list[DataDiligenceRiskMatrixEntry]` on `DataEvidenceSnapshotResponse`.

- [ ] **Step 1: Add backend expected fixture**

Add `_expected_diligence_risk_matrix()` to `backend/tests/test_data_api.py`. It must group `_expected_diligence_exception_register()` by `(severity_code, owner_area, related_artifact)` in severity order `critical`, `high`, `medium`.

The first expected entry must be:

```python
{
    "matrix_key": "risk_critical_email_ingestion_acquisition_readiness_summary_json",
    "severity_code": "critical",
    "owner_area": "email_ingestion",
    "related_artifact": "acquisition-readiness-summary.json",
    "exception_count": 2,
    "representative_exception_keys": [
        "exception_repair_thread_id_integrity",
        "exception_backfill_dedupe_fingerprints",
    ],
    "risk_label": "Critical close blocker concentration",
    "buyer_implication": (
        "2 critical exception(s) in email_ingestion affect "
        "acquisition-readiness-summary.json and block buyer close."
    ),
    "recommended_next_action": (
        "Resolve exception_repair_thread_id_integrity, "
        "exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot."
    ),
    "blocks_close": True,
    "provider_write_executed": False,
}
```

The final expected entry must be `risk_medium_attachment_parsing_remediation_actions_json`, severity `medium`, exception count `1`, related artifact `remediation-actions.json`, and `blocks_close: True`.

- [ ] **Step 2: Add model and grouping helper**

In `backend/api/data.py`, add `DataDiligenceRiskMatrixEntry` and `_diligence_risk_matrix(snapshot)`. The helper must only read `snapshot.diligence_exception_register`, group by `(severity_code, owner_area, related_artifact)`, and use existing severity values.

- [ ] **Step 3: Add deterministic labels and keys**

Add private helpers or constants for severity rank and labels:

```python
_RISK_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2}
_RISK_LABEL_BY_SEVERITY = {
    "critical": "Critical close blocker concentration",
    "high": "High diligence evidence gap",
    "medium": "Medium diligence coverage gap",
}
```

Build `matrix_key` by lowercasing and replacing non-alphanumeric separators with `_`, so `acquisition-readiness-summary.json` becomes `acquisition_readiness_summary_json`.

- [ ] **Step 4: Include matrix in digest**

Populate `diligence_risk_matrix` after `diligence_exception_register` and before `_snapshot_digest_payload(snapshot)` so `canonical_payload_fields` includes it.

- [ ] **Step 5: Run backend validation**

Run:

```bash
cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface tests/test_evidence_snapshot_verifier.py
cd backend && python -m ruff check api/data.py tests/test_data_api.py scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py
```

- [ ] **Step 6: Commit backend implementation**

Run:

```bash
git add backend/api/data.py backend/tests/test_data_api.py
git commit -m "feat: add diligence risk matrix"
```

### Task 2: Frontend Risk Matrix Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Test: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.diligence_risk_matrix`.
- Produces: an existing-style section titled `Diligence risk matrix` inside the `실사 스냅샷` card.

- [ ] **Step 1: Add TypeScript type and fixture**

Add `diligence_risk_matrix` to `DataEvidenceSnapshotResponse` and mirror the backend fixture in `frontend/src/app/data/page.test.tsx`.

- [ ] **Step 2: Render matrix entries**

Render each entry with severity badge, exception count, owner area, related artifact, risk label, buyer implication, recommended next action, close-blocker label, representative exception keys, and write boundary. Use existing card, typography, and safe text helpers.

- [ ] **Step 3: Assert UI and copied JSON**

Assert the UI contains `Diligence risk matrix`, `Critical close blocker concentration`, `2 critical exception(s)`, `email_ingestion`, `acquisition-readiness-summary.json`, and `exception_repair_thread_id_integrity`. Assert copied JSON has six matrix entries and the first matrix key is `risk_critical_email_ingestion_acquisition_readiness_summary_json`.

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
git commit -m "feat: show diligence risk matrix"
```

### Task 3: FigJam, Plan Completion, PR Update

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-diligence-risk-matrix.md`

- [ ] **Step 1: Generate FigJam flowchart**

Create a FigJam flowchart showing exception register rows -> severity/owner/artifact grouping -> risk matrix -> remediation priority -> buyer close decision.

- [ ] **Step 2: Run Ponytail diff review**

Review the diff for avoidable complexity. Expected acceptable result: no new dependency, no submodule, no speculative package split.

- [ ] **Step 3: Mark plan complete and commit**

Update all checkboxes to `[x]`, add execution evidence, and commit:

```bash
git add docs/superpowers/plans/2026-07-02-diligence-risk-matrix.md
git commit -m "docs: mark phase 24 plan complete"
```

- [ ] **Step 4: Push, update PR, verify live state**

Push to `plan/email-dom-paragraph-kg-2026-07-02`, append Phase 24 evidence to PR #895, and verify live `headRefOid`, checks, merge state, and unresolved review thread count.
