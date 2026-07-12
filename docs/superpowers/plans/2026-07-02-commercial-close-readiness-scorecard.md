# Commercial Close Readiness Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a buyer-facing commercial close readiness scorecard to the redacted DOM-paragraph knowledge-graph evidence snapshot for a 2,000,000,000 KRW target review.

**Architecture:** Keep the scorecard inside `DataEvidenceSnapshotResponse` and derive it only from already-redacted snapshot fields. Do not add a library, package, or submodule in this phase; the current repo already has the parser, evidence snapshot, release summary, and UI surfaces needed for the next buyer-diligence increment.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is metadata for readiness framing, not a valuation claim.
- The scorecard must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The scorecard must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Review process and queued GitHub checks are not blockers, but live PR head and thread/check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend Scorecard Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `DataEvidenceSnapshotResponse.acquisition_readiness_gate`, `evidence_packet_checklist`, `data_room_release_summary`, `diligence_close_acceptance_summary`, `verification_handoff`, `privacy_redaction_policy`
- Produces: `commercial_close_readiness_scorecard: DataCommercialCloseReadinessScorecard`

- [ ] Add `CommercialCloseReadinessStatus = Literal["commercially_ready", "commercially_blocked"]`.
- [ ] Add `CommercialCloseReadinessCategoryStatus = Literal["ready", "needs_attention"]`.
- [ ] Add `DataCommercialCloseReadinessCategoryScore` with `category_key`, `display_name`, `status_code`, `score`, `max_score`, and `detail_text`.
- [ ] Add `DataCommercialCloseReadinessScorecard` with target value, total score, category scores, blocker lists, buyer summary, next action, and `provider_write_executed`.
- [ ] Add `_default_commercial_close_readiness_scorecard()`.
- [ ] Add `_commercial_close_readiness_scorecard(snapshot)` after `_data_room_release_summary(snapshot)` is available.
- [ ] Populate `commercial_close_readiness_scorecard` before `_snapshot_digest_payload(snapshot)`.
- [ ] Add `_expected_commercial_close_readiness_scorecard()` and assert the exact object in `test_data_evidence_snapshot_returns_redacted_buyer_packet`.
- [ ] Assert `commercial_close_readiness_scorecard` is present in `canonical_payload_fields`.

Expected current fixture score:
- evidence packet integrity: 14 of 15
- data room release integrity: 14 of 20
- buyer acceptance clearance: 0 of 20
- privacy boundary: 20 of 20
- offline verification: 10 of 10
- product KPI attainment: 4 of 15
- total: 62 of 100
- status: `commercially_blocked`

### Task 2: Frontend Type And Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_readiness_scorecard`
- Produces: an existing-style snapshot card titled `Commercial close readiness`

- [ ] Add TypeScript types mirroring the backend scorecard contract.
- [ ] Add a fixture `commercialCloseReadinessScorecard` with the backend expected values.
- [ ] Add the scorecard to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [ ] Render the scorecard near the release summary using existing border/card/list/chip patterns.
- [ ] Show status, target value, score, buyer summary, next action, gap counts, privacy exposure count, verifier readiness, blocked artifacts, acceptance blocker keys, KPI gap keys, category scores, and write boundary.
- [ ] Assert visible text includes `Commercial close readiness`, `commercially_blocked`, `2,000,000,000 KRW`, `score 62 / 100`, `Product KPI attainment`, `exception_attach_kg_evidence_endpoints`, and `knowledge_graph_coverage`.
- [ ] Assert copied JSON includes `commercial_close_readiness_scorecard` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 33

- [ ] Generate a FigJam flowchart, not a Code Connect artifact.
- [ ] Diagram: acquisition gate, evidence packet, data-room release, acceptance summary, privacy policy, verifier handoff, and KPI targets feed the commercial close readiness scorecard.
- [ ] Record the FigJam URL in this plan.

### Task 4: Verification, Review, Push

**Files:**
- Modify: this plan's evidence section

**Interfaces:**
- Consumes: local tests, lint, git diff, PR #901 state
- Produces: pushed commit on `plan/email-dom-paragraph-kg-2026-07-02`

- [ ] Run `python3 -m pytest backend/tests/test_data_api.py -q`.
- [ ] Run `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py`.
- [ ] Run `npm test -- src/app/data/page.test.tsx`.
- [ ] Run `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx`.
- [ ] Run `git diff --check`.
- [ ] Run Ponytail review on the diff and record complexity verdict.
- [ ] Commit only intended files.
- [ ] Push to `origin HEAD:refs/heads/plan/email-dom-paragraph-kg-2026-07-02`.
- [ ] Re-verify live PR #901 `headRefOid`, merge state, unresolved review thread count, and check state.

## Evidence

- FigJam: `https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R`.
- Backend tests: `python3 -m pytest backend/tests/test_data_api.py -q` -> 9 passed, 1 skipped.
- Backend ruff: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` -> All checks passed.
- Frontend tests: `npm test -- src/app/data/page.test.tsx` -> 13 passed.
- Frontend lint: `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` -> passed.
- Diff check: `git diff --check` -> clean.
- Ponytail: `Lean already. Ship.`
- PR #901 live state: pending.
