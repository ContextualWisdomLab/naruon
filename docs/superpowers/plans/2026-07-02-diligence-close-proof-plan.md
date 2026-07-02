# Diligence Close Proof Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a buyer-facing diligence close proof plan to the redacted evidence snapshot so acquisition reviewers can see exactly which proof artifacts and acceptance criteria unblock close.

**Architecture:** Derive proof plan entries from the existing `diligence_risk_matrix`, not from raw email, attachment, database, or provider data. Keep the proof plan inside `DataEvidenceSnapshotResponse`, include it in the tamper-evident digest, and render it inside the existing `실사 스냅샷` card after the risk matrix.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, existing DataLayout styles.

## Global Constraints

- Do not use Figma Code Connect.
- Do not introduce a new library, package split, or git submodule in this phase.
- Keep all proof plan entries read-only with `provider_write_executed: false`.
- Do not expose raw email body, raw HTML, attachment bytes, stable provider IDs, database IDs, credentials, or database evidence column strings.
- Preserve unrelated dirty files: `.Jules/palette.md` and `.Jules/sentinel.md`.
- Treat queued review/check workflow state as non-blocking. Failed local validation or failed live checks are actionable.
- CodeGraph is absent in this worktree, so use focused file reads and `rg` for this phase.

---

### Task 1: Backend Close Proof Plan Contract

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `DataDiligenceCloseProofPlanEntry` with fields `proof_key`, `severity_code`, `owner_area`, `related_artifact`, `exception_count`, `required_proof_artifact`, `acceptance_criteria`, `verification_method`, `buyer_close_dependency`, `close_gate_status`, `next_action`, `provider_write_executed`.
- Produces: `diligence_close_proof_plan: list[DataDiligenceCloseProofPlanEntry]` on `DataEvidenceSnapshotResponse`.

- [x] **Step 1: Add backend expected fixture**

Add `_expected_diligence_close_proof_plan()` to `backend/tests/test_data_api.py`. It must produce one proof plan entry per `_expected_diligence_risk_matrix()` row in the same order.

The first expected entry must be:

```python
{
    "proof_key": "proof_risk_critical_email_ingestion_acquisition_readiness_summary_json",
    "severity_code": "critical",
    "owner_area": "email_ingestion",
    "related_artifact": "acquisition-readiness-summary.json",
    "exception_count": 2,
    "required_proof_artifact": "acquisition-readiness-summary.json",
    "acceptance_criteria": (
        "All 2 exception(s) for email_ingestion are resolved and "
        "acquisition-readiness-summary.json is regenerated without raw content or stable IDs."
    ),
    "verification_method": (
        "Regenerate the evidence snapshot and run python "
        "scripts/verify_evidence_snapshot.py <snapshot.json>."
    ),
    "buyer_close_dependency": "critical evidence gate",
    "close_gate_status": "blocked",
    "next_action": (
        "Resolve exception_repair_thread_id_integrity, "
        "exception_backfill_dedupe_fingerprints, then regenerate the evidence snapshot."
    ),
    "provider_write_executed": False,
}
```

The final expected entry must be `proof_risk_medium_attachment_parsing_remediation_actions_json`, severity `medium`, required proof artifact `remediation-actions.json`, and `close_gate_status: "blocked"`.

- [x] **Step 2: Add model and proof helper**

In `backend/api/data.py`, add `CloseGateStatus = Literal["blocked", "ready"]`, `DataDiligenceCloseProofPlanEntry`, and `_diligence_close_proof_plan(snapshot)`. The helper must only read `snapshot.diligence_risk_matrix`.

- [x] **Step 3: Add dependency labels**

Add `_CLOSE_DEPENDENCY_BY_SEVERITY`:

```python
_CLOSE_DEPENDENCY_BY_SEVERITY = {
    "critical": "critical evidence gate",
    "high": "high priority evidence gate",
    "medium": "coverage exception gate",
}
```

Use `close_gate_status="blocked"` when a risk entry `blocks_close` and `close_gate_status="ready"` otherwise.

- [x] **Step 4: Include proof plan in digest**

Populate `diligence_close_proof_plan` after `diligence_risk_matrix` and before `_snapshot_digest_payload(snapshot)` so `canonical_payload_fields` includes it.

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
git commit -m "feat: add diligence close proof plan"
```

### Task 2: Frontend Close Proof Plan Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Test: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.diligence_close_proof_plan`.
- Produces: an existing-style section titled `Diligence close proof plan` inside the `실사 스냅샷` card.

- [x] **Step 1: Add TypeScript type and fixture**

Add `diligence_close_proof_plan` to `DataEvidenceSnapshotResponse` and mirror the backend fixture in `frontend/src/app/data/page.test.tsx`.

- [x] **Step 2: Render proof plan entries**

Render each entry with severity badge, close gate status, owner area, required proof artifact, exception count, buyer-close dependency, acceptance criteria, verification method, next action, and write boundary. Use existing card, typography, and safe text helpers.

- [x] **Step 3: Assert UI and copied JSON**

Assert the UI contains `Diligence close proof plan`, `critical evidence gate`, `blocked`, `acquisition-readiness-summary.json`, `All 2 exception(s)`, and `verify_evidence_snapshot.py`. Assert copied JSON has six proof plan entries and the first proof key is `proof_risk_critical_email_ingestion_acquisition_readiness_summary_json`.

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
git commit -m "feat: show diligence close proof plan"
```

### Task 3: FigJam, Plan Completion, PR Update

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-diligence-close-proof-plan.md`

- [x] **Step 1: Generate FigJam flowchart**

Create a FigJam flowchart showing risk matrix -> close proof requirements -> acceptance criteria -> offline verification -> buyer close decision.

- [x] **Step 2: Run Ponytail diff review**

Review the diff for avoidable complexity. Expected acceptable result: no new dependency, no submodule, no speculative package split.

- [x] **Step 3: Mark plan complete and commit**

Update all checkboxes to `[x]`, add execution evidence, and commit:

```bash
git add docs/superpowers/plans/2026-07-02-diligence-close-proof-plan.md
git commit -m "docs: mark phase 25 plan complete"
```

- [x] **Step 4: Push, update PR, verify live state**

Push to `plan/email-dom-paragraph-kg-2026-07-02`, append Phase 25 evidence to PR #895, and verify live `headRefOid`, checks, merge state, and unresolved review thread count.

## Execution Evidence

- Plan commit: `9d8e3aa3 docs: plan diligence close proof plan`
- Backend implementation commit: `b4377eaf feat: add diligence close proof plan`
- Frontend implementation commit: `35335b2f feat: show diligence close proof plan`
- FigJam diagram: https://www.figma.com/board/WtZE5mxermJv53hWAtTnYg?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=bdf3f6ac-6623-4622-9a27-654b0e69715e
- Backend validation: `python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface tests/test_evidence_snapshot_verifier.py` -> `6 passed`; `python -m ruff check api/data.py tests/test_data_api.py scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py` -> `All checks passed!`
- Frontend validation: `npx vitest run src/app/data/page.test.tsx` -> `12 passed`; `git diff --check` -> clean.
- Ponytail complexity review: `Lean already. Ship.`
- Scope controls: no new library, no package split, no git submodule, no Figma Code Connect.
- Privacy controls: close proof plan is derived from redacted `diligence_risk_matrix`; `provider_write_executed` remains `false`.
- Worktree controls: `.Jules/palette.md` and `.Jules/sentinel.md` were preserved and not staged.
