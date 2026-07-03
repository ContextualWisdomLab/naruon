# Commercial Close Buyer Review Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic buyer review runbook to the redacted DOM-paragraph knowledge-graph evidence snapshot so a 2,000,000,000 KRW target review can see the exact review sequence, evidence files, blockers, verifier command, SLA cadence, and privacy/write guardrails.

**Architecture:** Keep the runbook inside `DataEvidenceSnapshotResponse` and derive it only from already-redacted snapshot fields, especially `commercial_close_release_package`. Do not add a new library, submodule, package split, route, dependency, or Figma Code Connect artifact in this phase; the contract still changes every phase, so extraction into a separate evidence-package library remains a follow-up after the snapshot surface stabilizes.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is buyer-review operating metadata, not a valuation claim.
- The runbook must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The runbook must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Review steps must come from already-redacted snapshot fields and existing diligence/commercial-close contracts, not new data sources.
- Review process and queued GitHub checks are not blockers, but live PR head, unresolved review-thread count, and check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend Buyer Review Runbook Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `commercial_close_release_package`, `privacy_redaction_policy`, `verification_handoff`, `data_room_release_summary`, `diligence_close_acceptance_summary`, `commercial_close_readiness_scorecard`, `commercial_close_execution_plan`, `commercial_close_kpi_operating_model`, `commercial_close_buyer_brief`, and `commercial_close_signoff_matrix`
- Produces: `commercial_close_buyer_review_runbook: DataCommercialCloseBuyerReviewRunbook`

- [x] Add `CommercialCloseBuyerReviewRunbookStatus = Literal["review_ready", "review_blocked"]`.
- [x] Add `CommercialCloseBuyerReviewStepStatus = Literal["ready", "blocked"]`.
- [x] Add `CommercialCloseBuyerReviewStepLane = Literal["intake", "verification", "privacy", "data_room", "commercial", "signoff", "release"]`.
- [x] Add `DataCommercialCloseBuyerReviewRunbookStep` with step key, review order, lane, status, evidence file, source field, reviewer role, owner area, SLA hours, review day, entry criteria, exit criteria, blocker keys, and privacy/write guardrails.
- [x] Add `DataCommercialCloseBuyerReviewRunbook` with target review metadata, status, step counts, blocked step keys, blocker keys, verifier command, buyer handoff, next action, first step, final decision step, steps, and write boundary.
- [x] Add `_default_commercial_close_buyer_review_runbook()`.
- [x] Add `_commercial_close_buyer_review_runbook(snapshot)` after `_commercial_close_release_package(snapshot)`.
- [x] Populate `commercial_close_buyer_review_runbook` before `_snapshot_digest_payload(snapshot)`.
- [x] Add `_expected_commercial_close_buyer_review_runbook()` and assert exact object equality in `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`.
- [x] Assert `commercial_close_buyer_review_runbook` is present in `canonical_payload_fields`.

Expected current fixture:
- status: `review_blocked`
- target review value: `2,000,000,000 KRW`
- steps: 11 review rows
- ready steps: 3
- blocked steps: 8
- first step: `buyer_review_intake`
- final decision step: `buyer_review_release_decision`
- provider write boundary: false

### Task 2: Frontend Type And Buyer Review Runbook Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_buyer_review_runbook`
- Produces: an existing-style snapshot card titled `Commercial close buyer review runbook`

- [x] Add TypeScript types mirroring the backend runbook contract.
- [x] Add a fixture `commercialCloseBuyerReviewRunbook` with the backend expected values.
- [x] Add the runbook to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [x] Render the runbook after the release package using existing border/list/chip patterns.
- [x] Show status, target review value, step counts, first/final steps, blocked steps, blocker keys, verifier command, buyer handoff, next action, review order, lane, evidence file, source field, reviewer role, owner area, SLA hours, review day, entry/exit criteria, privacy flags, and write boundary.
- [x] Assert visible text includes `Commercial close buyer review runbook`, `buyer_review_intake`, `buyer_review_release_decision`, `review_blocked`, `blocked steps 8`, `commercial-close-signoff-matrix.json`, and `python scripts/verify_evidence_snapshot.py <snapshot.json>`.
- [x] Assert copied JSON includes `commercial_close_buyer_review_runbook` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 39

- [x] Generate a FigJam flowchart, not a Code Connect artifact.
- [x] Diagram: release package, privacy policy, verifier, buyer review lanes, blocked/ready steps, and final release decision.
- [x] Record the FigJam URL in this plan.

### Task 4: Verification, Ponytail Review, Push

**Files:**
- Modify: this plan's evidence section

**Interfaces:**
- Consumes: local tests, lint, git diff, PR #901 state
- Produces: pushed commit on `plan/email-dom-paragraph-kg-2026-07-02`

- [x] Run `.venv/bin/python -m pytest backend/tests/test_data_api.py -q`.
- [x] Run `.venv/bin/python -m ruff check backend/api/data.py backend/tests/test_data_api.py`.
- [x] Run `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` from `frontend/`.
- [x] Run `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` from `frontend/`.
- [x] Run `git diff --check`.
- [x] Run Ponytail review on the diff and record complexity verdict.
- [ ] Commit only intended files.
- [ ] Push to `origin HEAD:refs/heads/plan/email-dom-paragraph-kg-2026-07-02`.
- [ ] Re-verify live PR #901 `headRefOid`, merge state, unresolved review thread count, and check state.

## Evidence

- FigJam: [Phase 39 Commercial Close Buyer Review Runbook](https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R) generated without Figma Code Connect.
- Backend tests: `.venv/bin/python -m pytest backend/tests/test_data_api.py -q` passed with 9 passed, 1 skipped.
- Backend ruff: `.venv/bin/python -m ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend tests: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` passed with 1 file and 13 tests.
- Frontend lint: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- Diff check: `git diff --check` passed.
- Ponytail: Lean already. Ship. The buyer review runbook stays in the existing snapshot contract, adds no dependency, and avoids a premature library/submodule split.
- PR #901 live state: pending.
