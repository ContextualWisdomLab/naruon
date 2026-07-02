# Commercial Close Signoff Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic role-by-role commercial close signoff matrix to the redacted DOM-paragraph knowledge-graph evidence snapshot so a 2,000,000,000 KRW target buyer review can see which operating roles can sign off and which blockers prevent close.

**Architecture:** Keep the signoff matrix inside `DataEvidenceSnapshotResponse` and derive it only from existing redacted snapshot fields. Do not add a new library, submodule, package split, route, dependency, or Figma Code Connect artifact in this phase; `backend/api/data.py` is large enough to justify a later internal split, but adding that split in the same PR would broaden the risk beyond this buyer-close artifact.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is role signoff review metadata, not a valuation claim.
- The signoff matrix must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The signoff matrix must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Signoff rows must come from already-redacted snapshot fields and existing diligence contracts, not new data sources.
- Review process and queued GitHub checks are not blockers, but live PR head, unresolved review-thread count, and check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend Signoff Matrix Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `commercial_close_buyer_brief`, `commercial_close_kpi_operating_model`, `commercial_close_execution_plan`, `commercial_close_readiness_scorecard`, `data_room_release_summary`, `diligence_close_acceptance_summary`, `privacy_redaction_policy`, and `verification_handoff`
- Produces: `commercial_close_signoff_matrix: DataCommercialCloseSignoffMatrix`

- [x] Add `CommercialCloseSignoffStatus = Literal["signed_off", "blocked"]`.
- [x] Add `CommercialCloseSignoffMatrixStatus = Literal["signoff_ready", "signoff_blocked"]`.
- [x] Add `DataCommercialCloseSignoffRow` with signoff key, reviewer role, owner area, status, source field, required artifact, blocker keys, acceptance text, next action, and write boundary.
- [x] Add `DataCommercialCloseSignoffMatrix` with target review metadata, matrix status, signoff counts, blocker keys, guardrail summary, reviewer handoff, next action, rows, and write boundary.
- [x] Add `_default_commercial_close_signoff_matrix()`.
- [x] Add `_commercial_close_signoff_matrix(snapshot)` after `_commercial_close_buyer_brief(snapshot)`.
- [x] Populate `commercial_close_signoff_matrix` before `_snapshot_digest_payload(snapshot)`.
- [x] Add `_expected_commercial_close_signoff_matrix()` and assert the exact object in `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`.
- [x] Assert `commercial_close_signoff_matrix` is present in `canonical_payload_fields`.

Expected current fixture:
- status: `signoff_blocked`
- target review value: `2,000,000,000 KRW`
- required signoffs: 7
- signed off: 3
- blocked: 4
- rows cover commercial diligence, program management, data-room operations, buyer diligence, privacy/security, verification, and security governance
- provider write boundary: false

### Task 2: Frontend Type And Signoff Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_signoff_matrix`
- Produces: an existing-style snapshot card titled `Commercial close signoff matrix`

- [x] Add TypeScript types mirroring the backend signoff matrix contract.
- [x] Add a fixture `commercialCloseSignoffMatrix` with the backend expected values.
- [x] Add the matrix to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [x] Render the matrix after the buyer brief using existing border/list/chip patterns.
- [x] Show status, target review value, signoff counts, blocker keys, guardrail summary, reviewer handoff, next action, row owners, source fields, artifacts, blocker keys, acceptance text, and write boundary.
- [x] Assert visible text includes `Commercial close signoff matrix`, `signoff_blocked`, `signoff_commercial_diligence`, `signoff_privacy_security`, `signoff_verification`, and `signoff_security_governance`.
- [x] Assert copied JSON includes `commercial_close_signoff_matrix` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 37

- [x] Generate a FigJam flowchart, not a Code Connect artifact.
- [x] Diagram: buyer brief, KPI model, execution plan, scorecard, release summary, acceptance summary, privacy policy, and verifier feed the signoff matrix.
- [x] Record the FigJam URL in this plan.

### Task 4: Verification, Ponytail Review, Push

**Files:**
- Modify: this plan's evidence section

**Interfaces:**
- Consumes: local tests, lint, git diff, PR #901 state
- Produces: pushed commit on `plan/email-dom-paragraph-kg-2026-07-02`

- [x] Run `python3 -m pytest backend/tests/test_data_api.py -q`.
- [x] Run `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py`.
- [x] Run `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` from `frontend/`.
- [x] Run `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` from `frontend/`.
- [x] Run `git diff --check`.
- [x] Run Ponytail review on the diff and record complexity verdict.
- [ ] Commit only intended files.
- [ ] Push to `origin HEAD:refs/heads/plan/email-dom-paragraph-kg-2026-07-02`.
- [ ] Re-verify live PR #901 `headRefOid`, merge state, unresolved review thread count, and check state.

## Evidence

- FigJam: [Phase 37 Commercial Close Signoff Matrix](https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R) generated without Figma Code Connect.
- Backend tests: `python3 -m pytest backend/tests/test_data_api.py -q` -> 9 passed, 1 skipped.
- Backend ruff: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` -> all checks passed.
- Frontend tests: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` -> 1 file passed, 13 tests passed.
- Frontend lint: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` -> clean.
- Diff check: `git diff --check` -> clean.
- Ponytail: `Lean already. Ship.`
- PR #901 live state: pending.
