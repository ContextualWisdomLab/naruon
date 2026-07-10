# Diligence Close Decision Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a buyer-facing diligence close decision summary to the redacted evidence snapshot so acquisition reviewers can immediately see whether close is blocked and why.

**Architecture:** Derive the summary from the existing `diligence_close_proof_plan`, not from raw email, attachment, database, or provider data. Keep the summary inside `DataEvidenceSnapshotResponse`, include it in the tamper-evident digest, and render it inside the existing `실사 스냅샷` card before detailed proof plan entries.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest, existing DataLayout styles.

## Global Constraints

- Do not use Figma Code Connect.
- Do not introduce a new library, package split, or git submodule in this phase.
- Keep the close decision summary read-only with `provider_write_executed: false`.
- Do not expose raw email body, raw HTML, attachment bytes, stable provider IDs, database IDs, credentials, or database evidence column strings.
- Preserve unrelated dirty files: `.Jules/palette.md` and `.Jules/sentinel.md`.
- Treat queued review/check workflow state as non-blocking. Failed local validation or failed live checks are actionable.
- CodeGraph tooling is not exposed in this session, so use focused file reads and `rg` for this phase.

---

### Task 1: Backend Close Decision Summary Contract

**Files:**
- Modify: `backend/api/data.py`
- Test: `backend/tests/test_data_api.py`

**Interfaces:**
- Produces: `DataDiligenceCloseDecisionSummary` with fields `summary_key`, `decision_code`, `total_proof_count`, `blocked_proof_count`, `ready_proof_count`, `critical_blocker_count`, `high_blocker_count`, `medium_blocker_count`, `required_artifact_count`, `required_artifacts`, `highest_severity`, `snapshot_verification_required`, `buyer_summary_text`, `next_action_text`, `provider_write_executed`.
- Produces: `diligence_close_decision_summary: DataDiligenceCloseDecisionSummary` on `DataEvidenceSnapshotResponse`.

- [x] **Step 1: Add backend expected fixture**

Add `_expected_diligence_close_decision_summary()` to `backend/tests/test_data_api.py`.

The expected fixture must be:

```python
{
    "summary_key": "buyer_close_decision",
    "decision_code": "close_blocked",
    "total_proof_count": 6,
    "blocked_proof_count": 6,
    "ready_proof_count": 0,
    "critical_blocker_count": 1,
    "high_blocker_count": 4,
    "medium_blocker_count": 1,
    "required_artifact_count": 5,
    "required_artifacts": [
        "acquisition-readiness-summary.json",
        "dom-paragraph-evidence-samples.json",
        "knowledge-graph-evidence-samples.json",
        "remediation-actions.json",
        "semantic-relation-evidence-samples.json",
    ],
    "highest_severity": "critical",
    "snapshot_verification_required": True,
    "buyer_summary_text": (
        "Close remains blocked by 6 proof requirement(s) across "
        "5 required artifact(s)."
    ),
    "next_action_text": (
        "Resolve critical and high proof blockers, regenerate the evidence "
        "snapshot, and verify the copied JSON with the offline snapshot verifier."
    ),
    "provider_write_executed": False,
}
```

- [x] **Step 2: Add model and helper**

In `backend/api/data.py`, add `DiligenceCloseDecision = Literal["ready_to_close", "close_blocked"]`, `DiligenceCloseSeverity = Literal["critical", "high", "medium", "none"]`, `DataDiligenceCloseDecisionSummary`, and `_diligence_close_decision_summary(snapshot)`.

The helper must only read `snapshot.diligence_close_proof_plan`.

- [x] **Step 3: Implement deterministic rollup**

Set:

```python
blocked = [item for item in snapshot.diligence_close_proof_plan if item.close_gate_status == "blocked"]
ready = [item for item in snapshot.diligence_close_proof_plan if item.close_gate_status == "ready"]
required_artifacts = sorted({item.required_proof_artifact for item in snapshot.diligence_close_proof_plan})
decision_code = "close_blocked" if blocked else "ready_to_close"
```

Use severity precedence `critical > high > medium > none`.

- [x] **Step 4: Include summary in digest**

Populate `diligence_close_decision_summary` after `diligence_close_proof_plan` and before `_snapshot_digest_payload(snapshot)` so `canonical_payload_fields` includes it.

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
git commit -m "feat: add diligence close decision summary"
```

### Task 2: Frontend Close Decision Summary Surface

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Test: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.diligence_close_decision_summary`.
- Produces: an existing-style section titled `Diligence close decision summary` inside the `실사 스냅샷` card.

- [x] **Step 1: Add TypeScript type and fixture**

Add `DiligenceCloseDecision`, `DiligenceCloseSeverity`, and `diligence_close_decision_summary` to `DataEvidenceSnapshotResponse`. Mirror the backend fixture in `frontend/src/app/data/page.test.tsx`.

- [x] **Step 2: Render summary**

Render decision code, buyer summary text, next action text, total/blocked/ready proof counts, severity blocker counts, required artifact count, highest severity, snapshot verification requirement, write boundary, and required artifact chips. Use existing card, typography, and safe text helpers.

- [x] **Step 3: Assert UI and copied JSON**

Assert the UI contains `Diligence close decision summary`, `close_blocked`, `Close remains blocked`, `6 proof requirement(s)`, `5 required artifact(s)`, `critical`, and `offline snapshot verifier`. Assert copied JSON includes the canonical field and exact summary shape.

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
git commit -m "feat: show diligence close decision summary"
```

### Task 3: FigJam, Plan Completion, PR Update

**Files:**
- Modify: `docs/superpowers/plans/2026-07-02-diligence-close-decision-summary.md`

- [x] **Step 1: Generate FigJam flowchart**

Create a FigJam flowchart showing close proof plan -> summary rollup -> close blocked/ready decision -> buyer action.

- [x] **Step 2: Run Ponytail diff review**

Review the diff for avoidable complexity. Expected acceptable result: no new dependency, no submodule, no speculative package split.

- [x] **Step 3: Mark plan complete and commit**

Update all checkboxes to `[x]`, add execution evidence, and commit:

```bash
git add docs/superpowers/plans/2026-07-02-diligence-close-decision-summary.md
git commit -m "docs: mark phase 26 plan complete"
```

- [x] **Step 4: Push, update PR, verify live state**

Push to `plan/email-dom-paragraph-kg-2026-07-02`, append Phase 26 evidence to PR #895, and verify live `headRefOid`, checks, merge state, and unresolved review thread count.

## Execution Evidence

- Plan commit: `ca475d4c docs: plan diligence close decision summary`
- Backend implementation commit: `7e4d35a8 feat: add diligence close decision summary`
- Frontend implementation commit: `b49efad9 feat: show diligence close decision summary`
- FigJam diagram: https://www.figma.com/board/bSTIfU3xqJvplXwW3mvgfe?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=23d5d677-10c2-4835-a0ed-9e2b67dab322
- Backend validation: `python -m pytest -q tests/test_data_api.py::test_data_quality_evidence_snapshot_returns_shareable_redacted_surface tests/test_evidence_snapshot_verifier.py` -> `6 passed`; `python -m ruff check api/data.py tests/test_data_api.py scripts/verify_evidence_snapshot.py tests/test_evidence_snapshot_verifier.py` -> `All checks passed!`
- Frontend validation: `npx vitest run src/app/data/page.test.tsx` -> `12 passed`; `git diff --check` -> clean.
- Ponytail complexity review: `Lean already. Ship.`
- Scope controls: no new library, no package split, no git submodule, no Figma Code Connect.
- Privacy controls: close decision summary is derived from redacted `diligence_close_proof_plan`; `provider_write_executed` remains `false`.
- Worktree controls: `.Jules/palette.md` and `.Jules/sentinel.md` were preserved and not staged.
