# Commercial Close Release Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic buyer data-room commercial close release package to the redacted DOM-paragraph knowledge-graph evidence snapshot so a 2,000,000,000 KRW target review can see the exact close artifacts, release order, blockers, verifier command, and guardrails.

**Architecture:** Keep the release package inside `DataEvidenceSnapshotResponse` and derive it only from existing redacted snapshot fields. Do not add a new library, submodule, package split, route, dependency, or Figma Code Connect artifact in this phase; this is a narrow canonical snapshot extension, while extraction into a dedicated evidence-package library is a later refactor once the contract stabilizes.

**Tech Stack:** FastAPI/Pydantic backend, existing Data API snapshot contract, React/TypeScript Data Quality UI, Vitest, Pytest, Ruff, FigJam diagram generation.

## Global Constraints

- Figma Code Connect is not used.
- `target_contract_value_krw` is release-review operating metadata, not a valuation claim.
- The release package must not expose raw email bodies, raw HTML, attachment bytes, message IDs, attachment IDs, stable database IDs, provider credentials, or DB evidence column strings.
- The release package must be deterministic for the same snapshot inputs and included in `canonical_payload_fields`.
- Release artifact rows must come from already-redacted snapshot fields and existing diligence/commercial-close contracts, not new data sources.
- Review process and queued GitHub checks are not blockers, but live PR head, unresolved review-thread count, and check state must be re-verified before completion.
- Preserve unrelated `.Jules/palette.md` and `.Jules/sentinel.md` edits.

---

### Task 1: Backend Release Package Contract

**Files:**
- Modify: `backend/api/data.py`
- Modify: `backend/tests/test_data_api.py`

**Interfaces:**
- Consumes: `data_room_package_manifest`, `data_room_release_summary`, `diligence_close_acceptance_summary`, `commercial_close_readiness_scorecard`, `commercial_close_execution_plan`, `commercial_close_kpi_operating_model`, `commercial_close_buyer_brief`, `commercial_close_signoff_matrix`, `privacy_redaction_policy`, and `verification_handoff`
- Produces: `commercial_close_release_package: DataCommercialCloseReleasePackage`

- [x] Add `CommercialCloseReleaseArtifactStatus = Literal["ready", "blocked"]`.
- [x] Add `CommercialCloseReleasePackageStatus = Literal["release_ready", "release_blocked"]`.
- [x] Add `CommercialCloseReleaseArtifactGroup = Literal["core_evidence", "commercial_close", "buyer_diligence", "guardrail"]`.
- [x] Add `DataCommercialCloseReleaseArtifact` with artifact key, release order, file name, display name, artifact group, status, source field, required artifact, reviewer role, blocker keys, release instruction text, raw/stable exposure booleans, and write boundary.
- [x] Add `DataCommercialCloseReleasePackage` with target review metadata, release status, artifact counts, signoff counts, blocked artifact files, blocker keys, verifier command, buyer handoff, next action, artifacts, and write boundary.
- [x] Add `_default_commercial_close_release_package()`.
- [x] Add `_commercial_close_release_package(snapshot)` after `_commercial_close_signoff_matrix(snapshot)`.
- [x] Populate `commercial_close_release_package` before `_snapshot_digest_payload(snapshot)`.
- [x] Add `_expected_commercial_close_release_package()` and assert the exact object in `test_data_quality_evidence_snapshot_returns_shareable_redacted_surface`.
- [x] Assert `commercial_close_release_package` is present in `canonical_payload_fields`.

Expected current fixture:
- status: `release_blocked`
- target review value: `2,000,000,000 KRW`
- artifacts: 10 release rows
- ready artifacts: 3
- blocked artifacts: 7
- signoffs: 3 signed off, 4 blocked
- provider write boundary: false

### Task 2: Frontend Type And Release Package Card

**Files:**
- Modify: `frontend/src/components/data-layout/types.ts`
- Modify: `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Modify: `frontend/src/app/data/page.test.tsx`

**Interfaces:**
- Consumes: `dataEvidenceSnapshot.commercial_close_release_package`
- Produces: an existing-style snapshot card titled `Commercial close release package`

- [x] Add TypeScript types mirroring the backend release package contract.
- [x] Add a fixture `commercialCloseReleasePackage` with the backend expected values.
- [x] Add the package to `canonical_payload_fields` and `dataEvidenceSnapshot`.
- [x] Render the package after the signoff matrix using existing border/list/chip patterns.
- [x] Show status, target review value, artifact counts, signoff counts, blocked files, blocker keys, verifier command, buyer handoff, next action, row order, row files, source fields, reviewer roles, release instructions, privacy flags, and write boundary.
- [x] Assert visible text includes `Commercial close release package`, `commercial-close-signoff-matrix.json`, `commercial-close-buyer-brief.json`, `release_blocked`, `blocked artifacts`, and `python scripts/verify_evidence_snapshot.py <snapshot.json>`.
- [x] Assert copied JSON includes `commercial_close_release_package` exactly.

### Task 3: FigJam Planning Update

**Files:**
- Modify: this plan's evidence section after generation

**Interfaces:**
- Consumes: current FigJam board `mjH0tpDIvz5kj44kL6354R`
- Produces: a new editable FigJam diagram for Phase 38

- [x] Generate a FigJam flowchart, not a Code Connect artifact.
- [x] Diagram: redacted evidence, diligence summaries, commercial-close scorecard/plan/KPI/brief/signoff, verifier, and buyer data-room release package.
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

- FigJam: [Phase 38 Commercial Close Release Package](https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R) generated without Figma Code Connect.
- Backend tests: `python3 -m pytest backend/tests/test_data_api.py -q` passed with 9 passed, 1 skipped.
- Backend ruff: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend tests: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm test -- src/app/data/page.test.tsx` passed with 1 file and 13 tests.
- Frontend lint: `PATH=/opt/homebrew/opt/node@24/bin:$PATH /opt/homebrew/opt/node@24/bin/npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- Diff check: `git diff --check` passed.
- Ponytail: Lean already. Ship. The release package stays in the existing snapshot contract, adds no dependency, and avoids a premature library/submodule split.
- PR #901 live state: pending.
