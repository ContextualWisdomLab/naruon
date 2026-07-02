# Diligence Exception Register Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a buyer-facing diligence exception register to the redacted evidence snapshot so acquisition reviewers can track remaining evidence gaps through remediation and close decisions.

**Architecture:** Derive exception entries from the existing acquisition readiness remediation actions and quality checks. Keep the register inside `DataEvidenceSnapshotResponse`, include it in the tamper-evident digest, and render it inside the existing `실사 스냅샷` card.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, existing DataLayout styles.

## Global Constraints

- Do not use Figma Code Connect.
- Do not introduce a new library, package split, or git submodule in this phase.
- Keep all exception entries read-only with `provider_write_executed: false`.
- Do not expose raw email body, raw HTML, attachment bytes, stable provider IDs, database IDs, credentials, or database evidence column strings.
- Preserve unrelated dirty files: `.Jules/palette.md` and `.Jules/sentinel.md`.
- Treat queued review/check workflow state as non-blocking. Failed local validation or failed live checks are actionable.

---

### Task 1: Backend Exception Register Contract

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `DataDiligenceExceptionRegisterEntry` with fields `exception_key`, `blocking_check_key`, `display_name`, `severity_code`, `owner_area`, `source_field`, `related_artifact`, `blocks_close`, `detail_text`, `next_action`, `provider_write_executed`.
- Produces: `diligence_exception_register: list[DataDiligenceExceptionRegisterEntry]` on `DataEvidenceSnapshotResponse`.

- [x] **Step 1: Add backend expected fixture**

Add `_expected_diligence_exception_register()` to `backend/tests/test_data_api.py`. It must produce one exception per existing remediation action and assert the first entry is:

```python
{
    "exception_key": "exception_repair_thread_id_integrity",
    "blocking_check_key": "thread_id_integrity",
    "display_name": "Canonical thread repair",
    "severity_code": "critical",
    "owner_area": "email_ingestion",
    "source_field": "quality_checks.thread_id_integrity",
    "related_artifact": "acquisition-readiness-summary.json",
    "blocks_close": True,
    "detail_text": "Thread provenance must be stable before buyer review.",
    "next_action": "Run canonical threading repair for affected scoped emails.",
    "provider_write_executed": False,
}
```

The final expected entry must be `exception_expand_attachment_parse_coverage`, severity `medium`, related artifact `remediation-actions.json`, and `blocks_close: True`.

- [x] **Step 2: Add model and helper**

In `backend/api/data.py`, add `DataDiligenceExceptionRegisterEntry` and reuse `RemediationPriority` for exception severity. Add `_diligence_exception_register(snapshot)` that maps `snapshot.acquisition_readiness_gate.remediation_actions` to safe exception rows.

- [x] **Step 3: Add safe source/artifact maps**

Add `_EXCEPTION_SOURCE_FIELD_BY_CHECK_KEY` and `_EXCEPTION_ARTIFACT_BY_CHECK_KEY` dictionaries. Values must be safe logical fields or safe data-room filenames, not database column evidence strings.

- [x] **Step 4: Include register in digest**

Populate `diligence_exception_register` before `_snapshot_digest_payload(snapshot)` so `canonical_payload_fields` includes it.

- [x] **Step 5: Run backend validation**

Run:

```bash
cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface tests/test_evidence_snapshot_verifier.py
cd backend && python -m ruff check api/data.py tests/test_data_api.py scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py
```

- [x] **Step 6: Commit backend implementation**

Run:

```bash
git add backend/api/data.py backend/tests/test_data_api.py
git commit -m "feat: add diligence exception register"
```

### Task 2: Frontend Exception Register Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Test: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.diligence_exception_register`.
- Produces: an existing-style section titled `Diligence exception register` inside the `실사 스냅샷` card.

- [x] **Step 1: Add TypeScript type and fixture**

Add `diligence_exception_register` to `DataEvidenceSnapshotResponse` and mirror the backend fixture in `frontend/src/app/data/page.test.tsx`.

- [x] **Step 2: Render exception entries**

Render each entry with severity badge, owner area, source field, related artifact, close-blocker label, detail text, next action, and write boundary. Use existing card, typography, status, and safe text helpers.

- [x] **Step 3: Assert UI and copied JSON**

Assert the UI contains `Diligence exception register`, `Canonical thread repair`, `critical`, `acquisition-readiness-summary.json`, `blocks close: yes`, and `Run canonical threading repair`. Assert copied JSON has nine entries and the first exception key is `exception_repair_thread_id_integrity`.

- [x] **Step 4: Run frontend validation**

Run:

```bash
cd frontend && npx vitest run src/app/data/page.test.tsx
git diff --check
```

- [x] **Step 5: Commit frontend implementation**

Run:

```bash
git add frontend/src/components/data-layout/types.ts frontend/src/components/data-layout/QualityCheckTab.tsx frontend/src/app/data/page.test.tsx
git commit -m "feat: show diligence exception register"
```

### Task 3: FigJam, Plan Completion, PR Update

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-diligence-exception-register.md`

- [x] **Step 1: Generate FigJam flowchart**

Create a FigJam flowchart showing quality checks -> remediation actions -> exception register -> data-room artifacts -> buyer close decision.

- [x] **Step 2: Run Ponytail diff review**

Review the diff for avoidable complexity. Expected acceptable result: no new dependency, no submodule, no speculative package split.

- [x] **Step 3: Mark plan complete and commit**

Update all checkboxes to `[x]`, add execution evidence, and commit:

```bash
git add docs/superpowers/plans/2026-07-02-diligence-exception-register.md
git commit -m "docs: mark phase 23 plan complete"
```

- [x] **Step 4: Push, update PR, verify live state**

Push to `plan/email-dom-paragraph-kg-2026-07-02`, append Phase 23 evidence to PR #895, and verify live `headRefOid`, checks, merge state, and unresolved review thread count.

## Execution Evidence

- Backend contract and digest inclusion implemented in `85d338dd`; frontend rendering and copied JSON coverage implemented in `6d6959ec`.
- Ponytail review found one avoidable duplicate severity alias. It was removed in `a9e1c8c5` by reusing `RemediationPriority`; follow-up status: `Lean already. Ship.`
- FigJam flowchart: https://www.figma.com/board/PFEqLCsHLMTrUgv4CeIBMf
- Validation:
  - `cd backend && python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface tests/test_evidence_snapshot_verifier.py` -> 6 passed.
  - `cd backend && python -m ruff check api/data.py tests/test_data_api.py scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py` -> passed.
  - `cd frontend && npx vitest run src/app/data/page.test.tsx` -> 12 passed.
  - `git diff --check` -> passed.
- No new dependency, package split, git submodule, or Figma Code Connect usage was introduced.
- Unrelated dirty files `.Jules/palette.md` and `.Jules/sentinel.md` were preserved.
