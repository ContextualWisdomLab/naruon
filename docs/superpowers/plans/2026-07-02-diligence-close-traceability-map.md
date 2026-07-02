# Diligence Close Traceability Map

## Goal

Add a deterministic buyer-close traceability map to the redacted evidence snapshot so buyers can follow each safe DOM/paragraph, attachment, and knowledge-graph evidence artifact from source field through exception, risk, proof, artifact review, and owner handoff.

## Scope

- Keep the work inside the existing `backend/api/data.py` evidence snapshot contract and `frontend/src/components/data-layout` UI.
- Do not create a separate library, git submodule, or package for this phase; the trace map is a deterministic join over existing snapshot sections.
- Do not use Figma Code Connect.
- Do not expose raw email bodies, raw attachment content, stable provider IDs, provider credentials, database evidence strings, raw sample identifiers, or raw provider source paths.
- Preserve unrelated `.Jules` working tree changes.

## Implementation Plan

- [x] Add `diligence_close_traceability_map` to the evidence snapshot response.
- [x] Derive trace entries from `diligence_close_proof_plan`, joined to `diligence_risk_matrix`, `data_room_package_manifest`, `diligence_close_artifact_review_queue`, and `diligence_close_owner_handoff_queue`.
- [x] Include source field, data-room artifact, manifest key, exception keys, risk key, proof key, artifact review key, owner handoff key, owner area, severity, exception count, close gate status, reviewer roles, trace summary, next action, snapshot verification requirement, and write boundary.
- [x] Include the field in the canonical digest payload and backend fixture assertions.
- [x] Add a UI section after the owner handoff queue and before the detailed proof plan.
- [x] Add frontend fixture, copied JSON, and visible rendering coverage.
- [x] Generate a FigJam diagram for the traceability-map flow without Code Connect.
- [x] Run backend tests, ruff, frontend tests, frontend lint, diff review, and Ponytail review.
- [x] Push the PR branch and update PR #895 with Phase 29 evidence.

## Acceptance Criteria

- The first trace item links `acquisition_readiness_gate` to `acquisition-readiness-summary.json`, `risk_critical_email_ingestion_acquisition_readiness_summary_json`, `proof_risk_critical_email_ingestion_acquisition_readiness_summary_json`, `review_acquisition_readiness_summary_json`, and `handoff_email_ingestion`.
- DOM paragraph evidence traceability is represented by `content_graph_evidence_samples` feeding `dom-paragraph-evidence-samples.json`.
- Knowledge graph evidence traceability is represented by `knowledge_graph_evidence_samples` feeding `knowledge-graph-evidence-samples.json`.
- Attachment remediation traceability is represented by `acquisition_readiness_gate.remediation_actions` feeding `remediation-actions.json`.
- Every trace entry has `provider_write_executed: false`.
- `canonical_payload_fields` includes `diligence_close_traceability_map`.
- The copied evidence snapshot JSON includes the new traceability map.
- The UI renders source field, data-room artifact, exception keys, risk key, proof key, review/handoff keys, reviewer roles, next action, snapshot verification, and write boundary.
- Local backend and frontend validations pass.

## Evidence

- Backend model/API: `diligence_close_traceability_map` is derived deterministically from existing snapshot sections before canonical digest generation.
- Backend coverage: `python3 -m pytest backend/tests/test_data_api.py -q` passed with 9 passed and 1 skipped.
- Backend lint: `ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend coverage: `npm test -- src/app/data/page.test.tsx` passed with 12 tests.
- Frontend lint: `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- FigJam: https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R
- Ponytail review: removed speculative missing-join fallbacks and kept the trace map inside the existing evidence snapshot and Data Quality UI contract; no separate library, package, or submodule is warranted for this phase.
- PR #895 was updated with Phase 29 evidence after pushing head `1efc31f67715f4324e20c37759ecb9d8ac1cfd30`; live state was mergeable, blocked only by queued checks, with 0 unresolved review threads at that verification point.
