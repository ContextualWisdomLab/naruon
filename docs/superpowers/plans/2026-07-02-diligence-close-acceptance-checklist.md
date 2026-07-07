# Diligence Close Acceptance Checklist

## Goal

Add a deterministic buyer-close acceptance checklist to the redacted evidence snapshot so diligence reviewers can approve each safe DOM/paragraph, attachment, and knowledge-graph evidence artifact from the traceability map without receiving raw email bodies, raw attachment bytes, stable identifiers, provider credentials, or database evidence strings.

## Scope

- Keep the work inside the existing `backend/api/data.py` evidence snapshot contract and `frontend/src/components/data-layout` Data Quality UI.
- Do not create a separate library, package, git submodule, or Figma Code Connect integration for this phase; the checklist is a deterministic view over the existing traceability map and verifier handoff.
- Preserve unrelated `.Jules` working tree changes.
- Treat review process and queued GitHub checks as non-blocking per operator instruction.

## Implementation Plan

- [x] Add `diligence_close_acceptance_checklist` to the evidence snapshot response.
- [x] Derive acceptance entries from `diligence_close_traceability_map` plus `verification_handoff.verifier_command`.
- [x] Include acceptance key, trace key, data-room artifact, source field, owner area, reviewer roles, acceptance status, close gate status, blocker keys, acceptance criteria, verifier command, reviewer summary, next action, snapshot verification requirement, and write boundary.
- [x] Include the field in the canonical digest payload and backend fixture assertions.
- [x] Add a UI section after the traceability map and before the detailed proof plan.
- [x] Add frontend fixture, copied JSON, and visible rendering coverage.
- [x] Add the Phase 30 FigJam flow without Figma Code Connect.
- [x] Run backend tests, ruff, frontend tests, and frontend lint.

## Acceptance Criteria

- The first acceptance item links `trace_risk_critical_email_ingestion_acquisition_readiness_summary_json` to `acquisition-readiness-summary.json`, `acquisition_readiness_gate`, `email_ingestion`, and `executive diligence reviewer`.
- DOM paragraph acceptance is represented by `content_graph_evidence_samples` feeding `dom-paragraph-evidence-samples.json`.
- Knowledge graph acceptance is represented by `knowledge_graph_evidence_samples` feeding `knowledge-graph-evidence-samples.json`.
- Attachment remediation acceptance keeps `exception_expand_attachment_parse_coverage` visible as a blocker key.
- Every checklist entry has `provider_write_executed: false`.
- `canonical_payload_fields` includes `diligence_close_acceptance_checklist`.
- The copied evidence snapshot JSON includes the new acceptance checklist.
- The UI renders acceptance criteria, verifier command, close gate, blocker keys, reviewer roles, next action, snapshot verification, and write boundary.
- Local backend and frontend validations pass.

## Evidence

- Backend model/API: `diligence_close_acceptance_checklist` is derived deterministically from the traceability map before canonical digest generation.
- Backend coverage: `python3 -m pytest backend/tests/test_data_api.py -q` passed with 9 passed and 1 skipped.
- Backend lint: `ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend coverage: `npm test -- src/app/data/page.test.tsx` passed with 12 tests.
- Frontend lint: `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- FigJam: https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R
- Product/design decision: no separate library or submodule is warranted yet because the acceptance checklist is a narrow deterministic projection of the existing snapshot contract and UI surface.
