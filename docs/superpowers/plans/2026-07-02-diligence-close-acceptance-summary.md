# Diligence Close Acceptance Summary

## Goal

Add a deterministic buyer-close acceptance summary to the redacted evidence snapshot so acquisition reviewers can see the acceptance decision, required reviewer roles, data-room artifacts, blocker keys, verifier action, and write boundary without opening every checklist item.

## Scope

- Keep the work inside the existing `backend/api/data.py` evidence snapshot contract and `frontend/src/components/data-layout` Data Quality UI.
- Do not create a separate library, package, git submodule, or Figma Code Connect integration for this phase; the summary is a deterministic rollup over the existing acceptance checklist.
- Preserve unrelated `.Jules` working tree changes.
- Treat review process and queued GitHub checks as non-blocking per operator instruction.

## Implementation Plan

- [x] Add `DataDiligenceCloseAcceptanceSummary` to the evidence snapshot response.
- [x] Derive the summary from `diligence_close_acceptance_checklist` after the checklist is populated.
- [x] Include decision code, total/blocked/ready acceptance counts, reviewer roles, required artifacts, blocker keys, close gate, snapshot verification requirement, buyer summary, next action, and write boundary.
- [x] Include `diligence_close_acceptance_summary` in canonical payload fields and backend fixture assertions.
- [x] Add frontend TypeScript coverage and a Data Quality summary card before the detailed acceptance checklist.
- [x] Render reviewer role, required artifact, and blocker key chips using existing Data Quality card styles.
- [x] Extend frontend fixture, visible rendering assertions, and copied snapshot JSON assertions.
- [x] Add the Phase 31 FigJam flow without Figma Code Connect.
- [x] Run backend tests, ruff, frontend tests, frontend lint, and `git diff --check`.

## Acceptance Criteria

- The summary key is `buyer_close_acceptance`.
- `decision_code` is `close_blocked` when any acceptance checklist item is blocked; otherwise it is `ready_to_close`.
- `close_gate_status` mirrors the blocked/ready decision.
- The current evidence snapshot reports 6 total acceptance items, 6 blocked items, 0 ready items, 3 reviewer roles, 5 required artifacts, and 9 blocker keys.
- Required artifacts include `acquisition-readiness-summary.json`, `dom-paragraph-evidence-samples.json`, `knowledge-graph-evidence-samples.json`, `remediation-actions.json`, and `semantic-relation-evidence-samples.json`.
- Blocker keys include `exception_attach_kg_evidence_endpoints` and `exception_expand_attachment_parse_coverage`.
- `snapshot_verification_required` is true when any checklist item requires copied snapshot verification.
- `provider_write_executed` remains false.
- The UI renders the acceptance summary, buyer summary, verifier next action, counts, reviewer role chips, required artifact chips, blocker key chips, and write boundary.
- The copied evidence snapshot JSON includes the exact summary shape.

## Evidence

- Backend validation: `python3 -m pytest backend/tests/test_data_api.py -q` passed with 9 passed and 1 skipped.
- Backend lint: `python3 -m ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend coverage: `npm test -- src/app/data/page.test.tsx` passed with 12 tests.
- Frontend lint: `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- FigJam: https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R
- Ponytail complexity review: no new dependency, package split, submodule, or speculative abstraction is warranted for this deterministic snapshot projection.
- Product/design decision: no separate library or submodule is warranted yet because the summary is a narrow deterministic projection of the existing snapshot contract and UI surface.
