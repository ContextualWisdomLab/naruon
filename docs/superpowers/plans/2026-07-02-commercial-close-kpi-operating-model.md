# Commercial Close KPI Operating Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic commercial close KPI operating model to the redacted DOM-paragraph knowledge-graph evidence snapshot so a 2,000,000,000 KRW target buyer review can see the primary KPI, driver metrics, guardrails, owners, source fields, and next actions that govern close readiness.

**Architecture:** Keep the KPI model inside `DataEvidenceSnapshotResponse` and derive it only from existing redacted snapshot fields. Do not add a new library, submodule, package split, route, dependency, or Figma Code Connect artifact in this phase; the sale-readiness value comes from a stable API contract, digest inclusion, visible UI, and regression evidence.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is operational KPI review metadata, not a valuation claim.
- The KPI model must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The KPI model must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Metrics must come from already-redacted snapshot fields and existing buyer diligence contracts, not new data sources.
- Review process and queued GitHub checks are not blockers, but live PR head, unresolved review-thread count, and check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend KPI Operating Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `commercial_close_readiness_scorecard`, `commercial_close_execution_plan`, `data_room_release_summary`, `diligence_close_acceptance_summary`, `verification_handoff`, `privacy_redaction_policy`, and `acquisition_readiness_gate.kpis`
- Produces: `commercial_close_kpi_operating_model: DataCommercialCloseKpiOperatingModel`

- [x] Add `CommercialCloseKpiMetricKind = Literal["primary", "driver", "guardrail"]`.
- [x] Add `CommercialCloseKpiMetricStatus = Literal["target_met", "needs_attention"]`.
- [x] Add `CommercialCloseKpiOperatingStatus = Literal["operating_ready", "operating_blocked"]`.
- [x] Add `DataCommercialCloseKpiOperatingMetric` with metric key, kind, status, current/target values, unit, owner area, source field, buyer implication, next action, and write boundary.
- [x] Add `DataCommercialCloseKpiOperatingModel` with target review metadata, metric counts, blocker keys, buyer summary, next action, metrics, and write boundary.
- [x] Add `_default_commercial_close_kpi_operating_model()`.
- [x] Add `_commercial_close_kpi_operating_model(snapshot)` after `_commercial_close_execution_plan(snapshot)`.
- [x] Populate `commercial_close_kpi_operating_model` before `_snapshot_digest_payload(snapshot)`.
- [x] Add `_expected_commercial_close_kpi_operating_model()` and assert the exact object in `test_data_evidence_snapshot_returns_redacted_buyer_packet`.
- [x] Assert `commercial_close_kpi_operating_model` is present in `canonical_payload_fields`.

Expected current fixture:
- status: `operating_blocked`
- total metrics: 8
- target met: 3
- needs attention: 5
- primary metrics: 1
- driver metrics: 4
- guardrail metrics: 3
- primary score: 62 of 100

### Task 2: Frontend Type And KPI Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_kpi_operating_model`
- Produces: an existing-style snapshot card titled `Commercial close KPI operating model`

- [x] Add TypeScript types mirroring the backend KPI operating contract.
- [x] Add a fixture `commercialCloseKpiOperatingModel` with the backend expected values.
- [x] Add the model to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [x] Render the model near the commercial close execution plan using existing border/list/chip patterns.
- [x] Show status, target review value, metric counts, target-met count, needs-attention count, driver/guardrail counts, buyer summary, next action, metric ownership, source fields, current/target values, buyer implications, and write boundary.
- [x] Assert visible text includes `Commercial close KPI operating model`, `operating_blocked`, `commercial_close_readiness_score`, `execution_lane_clearance`, `privacy_exposure_control`, and `provider_write_boundary`.
- [x] Assert copied JSON includes `commercial_close_kpi_operating_model` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 35

- [x] Generate a FigJam flowchart, not a Code Connect artifact.
- [x] Diagram: readiness scorecard, execution plan, release summary, acceptance summary, acquisition KPIs, and guardrails feed the KPI operating model.
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

- FigJam: `https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R`.
- Backend tests: `python3 -m pytest backend/tests/test_data_api.py -q` -> 9 passed, 1 skipped.
- Backend ruff: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` -> All checks passed.
- Frontend tests: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` -> 13 passed.
- Frontend lint: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` -> passed with exit code 0.
- Diff check: `git diff --check` -> clean.
- Ponytail: `Lean already. Ship.`
- PR #901 live state: pending.
