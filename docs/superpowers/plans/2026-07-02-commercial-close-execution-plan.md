# Commercial Close Execution Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic commercial close execution plan to the redacted DOM-paragraph knowledge-graph evidence snapshot so a 2,000,000,000 KRW target buyer review can see exactly which owner lanes, artifacts, blockers, and verification steps remain before close.

**Architecture:** Keep this as a first-party `DataEvidenceSnapshotResponse` contract derived from already-redacted snapshot fields. Do not add a separate library, submodule, package split, or Figma Code Connect artifact in this phase; the value is in a stable buyer-facing API contract, digest inclusion, visible UI, and regression evidence.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is operational sale-readiness metadata, not a valuation claim.
- The plan must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The plan must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Execution lanes must be grouped from existing remediation actions and data-room artifacts, not hand-authored duplicate business logic.
- Review process and queued GitHub checks are not blockers, but live PR head, unresolved review-thread count, and check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend Execution Plan Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `commercial_close_readiness_scorecard`, `acquisition_readiness_gate.remediation_actions`, `data_room_package_manifest`, `diligence_close_acceptance_summary`, and `verification_handoff`
- Produces: `commercial_close_execution_plan: DataCommercialCloseExecutionPlan`

- [x] Add `CommercialCloseExecutionStatus = Literal["execution_ready", "execution_blocked"]`.
- [x] Add `CommercialCloseExecutionLaneStatus = Literal["ready", "blocked"]`.
- [x] Add `DataCommercialCloseExecutionLane` with execution order, owner area, priority, related artifact, action keys, blocker keys, acceptance criteria, verification command, and write boundary.
- [x] Add `DataCommercialCloseExecutionPlan` with target review metadata, lane/action counts, artifact list, KPI/blocker counts, buyer summary, next action, and lanes.
- [x] Add `_default_commercial_close_execution_plan()`.
- [x] Add `_commercial_close_execution_plan(snapshot)` after `_commercial_close_readiness_scorecard(snapshot)`.
- [x] Populate `commercial_close_execution_plan` before `_snapshot_digest_payload(snapshot)`.
- [x] Add `_expected_commercial_close_execution_plan()` and assert the exact object in `test_data_evidence_snapshot_returns_redacted_buyer_packet`.
- [x] Assert `commercial_close_execution_plan` is present in `canonical_payload_fields`.

Expected current fixture:
- status: `execution_blocked`
- total lanes: 6
- blocked lanes: 6
- critical lanes: 1
- high lanes: 4
- medium lanes: 1
- total actions: 9
- related artifacts: 5
- KPI gaps: 9
- acceptance blockers: 9

### Task 2: Frontend Type And Execution Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_execution_plan`
- Produces: an existing-style snapshot card titled `Commercial close execution plan`

- [x] Add TypeScript types mirroring the backend execution-plan contract.
- [x] Add a fixture `commercialCloseExecutionPlan` with the backend expected values.
- [x] Add the plan to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [x] Render the plan near the commercial close readiness scorecard using existing border/list/chip patterns.
- [x] Show status, target review value, lane counts, action counts, artifact counts, KPI gaps, blocker counts, verifier command, buyer summary, next action, lane ownership, artifact readiness, acceptance criteria, blocking check keys, acceptance blocker keys, action keys, and write boundary.
- [x] Assert visible text includes `Commercial close execution plan`, `execution_blocked`, `6 lane(s)`, `email_ingestion`, `acquisition-readiness-summary.json`, `thread_id_integrity`, and `exception_repair_thread_id_integrity`.
- [x] Assert copied JSON includes `commercial_close_execution_plan` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 34

- [x] Generate a FigJam flowchart, not a Code Connect artifact.
- [x] Diagram: readiness scorecard, remediation actions, data-room manifest, acceptance summary, and verifier handoff feed execution lanes, then buyer review reissue.
- [x] Record the FigJam URL in this plan.

### Task 4: Verification, Ponytail Review, Push

**Files:**
- Modify: this plan's evidence section

**Interfaces:**
- Consumes: local tests, lint, git diff, PR #901 state
- Produces: pushed commit on `plan/email-dom-paragraph-kg-2026-07-02`

- [x] Run `python3 -m pytest backend/tests/test_data_api.py -q`.
- [x] Run `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py`.
- [x] Run `npm test -- src/app/data/page.test.tsx`.
- [x] Run `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx`.
- [x] Run `git diff --check`.
- [x] Run Ponytail review on the diff and record complexity verdict.
- [x] Commit only intended files.
- [x] Push to `origin HEAD:refs/heads/plan/email-dom-paragraph-kg-2026-07-02`.
- [x] Re-verify live PR #901 `headRefOid`, merge state, unresolved review thread count, and check state.

## Evidence

- FigJam: `https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R`.
- Backend tests: `python3 -m pytest backend/tests/test_data_api.py -q` -> 9 passed, 1 skipped.
- Backend ruff: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` -> All checks passed.
- Frontend tests: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` from `frontend/` -> 13 passed.
- Frontend lint: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` from `frontend/` -> passed.
- Diff check: `git diff --check` -> clean.
- Ponytail: `Lean already. Ship.`
- PR #901 live state: branch head re-verified after push, review threads 5 unresolved total with 1 current and 4 outdated, GitHub checks pending/queued and not treated as blockers.
