# Commercial Close Buyer Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic buyer brief to the redacted DOM-paragraph knowledge-graph evidence snapshot so a 2,000,000,000 KRW target buyer review can read the close status, proof thesis, blocker summary, guardrails, and handoff without inspecting raw emails or attachments.

**Architecture:** Keep the buyer brief inside `DataEvidenceSnapshotResponse` and derive it only from existing redacted snapshot fields. Do not add a new library, submodule, package split, route, dependency, or Figma Code Connect artifact in this phase; the sale-readiness value comes from a stable API contract, digest inclusion, visible UI, and regression evidence.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is buyer-review operating metadata, not a valuation claim.
- The buyer brief must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The buyer brief must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Brief bullets must come from already-redacted snapshot fields and existing diligence contracts, not new data sources.
- Review process and queued GitHub checks are not blockers, but live PR head, unresolved review-thread count, and check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend Buyer Brief Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `diligence_close_decision_summary`, `acquisition_readiness_gate`, `data_room_release_summary`, `commercial_close_readiness_scorecard`, `commercial_close_execution_plan`, `commercial_close_kpi_operating_model`, `diligence_exception_register`, `privacy_redaction_policy`, and `verification_handoff`
- Produces: `commercial_close_buyer_brief: DataCommercialCloseBuyerBrief`

- [x] Add `CommercialCloseBuyerBriefStatus = Literal["brief_ready", "brief_blocked"]`.
- [x] Add `DataCommercialCloseBuyerBriefBullet` with bullet key, display label, source field, detail text, and provider write boundary.
- [x] Add `DataCommercialCloseBuyerBrief` with target review metadata, status, readiness headline, proof thesis, evidence basis bullets, blocker bullets, guardrail bullets, reviewer handoff text, next action, and write boundary.
- [x] Add `_default_commercial_close_buyer_brief()`.
- [x] Add `_commercial_close_buyer_brief(snapshot)` after `_commercial_close_kpi_operating_model(snapshot)`.
- [x] Populate `commercial_close_buyer_brief` before `_snapshot_digest_payload(snapshot)`.
- [x] Add `_expected_commercial_close_buyer_brief()` and assert the exact object in `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`.
- [x] Assert `commercial_close_buyer_brief` is present in `canonical_payload_fields`.

Expected current fixture:
- status: `brief_blocked`
- target review value: `2,000,000,000 KRW`
- readiness headline includes readiness score `62/100`
- proof thesis references redacted DOM/paragraph/KG evidence, data-room readiness, buyer acceptance, KPI operating status, and offline verification
- top blocker bullets: 5
- guardrail bullets: 4
- provider write boundary: false

### Task 2: Frontend Type And Buyer Brief Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_buyer_brief`
- Produces: an existing-style snapshot card titled `Commercial close buyer brief`

- [x] Add TypeScript types mirroring the backend buyer brief contract.
- [x] Add a fixture `commercialCloseBuyerBrief` with the backend expected values.
- [x] Add the brief to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [x] Render the brief near the commercial close KPI operating model using existing border/list/chip patterns.
- [x] Show status, target review value, readiness headline, proof thesis, reviewer handoff, next action, evidence basis bullets, blocker bullets, guardrail bullets, and write boundary.
- [x] Assert visible text includes `Commercial close buyer brief`, `brief_blocked`, `buyer_brief_readiness_score`, `buyer_brief_kpi_operating_model`, `buyer_brief_privacy_redaction`, and `buyer_brief_offline_verifier`.
- [x] Assert copied JSON includes `commercial_close_buyer_brief` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 36

- [x] Generate a FigJam flowchart, not a Code Connect artifact.
- [x] Diagram: decision summary, readiness gate, release summary, scorecard, execution plan, KPI model, exception register, privacy policy, and verifier feed the buyer brief.
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
- [x] Commit only intended files.
- [x] Push to `origin HEAD:refs/heads/plan/email-dom-paragraph-kg-2026-07-02`.
- [x] Re-verify live PR #901 `headRefOid`, merge state, unresolved review thread count, and check state.

## Evidence

- FigJam: `https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R`.
- Backend tests: `python3 -m pytest backend/tests/test_data_api.py -q` -> 9 passed, 1 skipped.
- Backend ruff: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` -> All checks passed.
- Frontend tests: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` -> 13 passed.
- Frontend lint: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` -> passed with exit code 0.
- Diff check: `git diff --check` -> clean.
- Ponytail: `Lean already. Ship.`
- PR #901 live state after implementation push: `headRefOid=64b782e8d64b3d91e9e0e1701e4ea48953f0b024`, `mergeable=MERGEABLE`, `mergeStateStatus=BLOCKED`, current unresolved review threads `0`, outdated unresolved review threads `4`, checks queued/pending.
