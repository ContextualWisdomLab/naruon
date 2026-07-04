# Diligence Close Artifact Review Queue

## Goal

Add a deterministic buyer-close artifact review queue to the redacted evidence snapshot so a diligence reviewer can see which safe data-room artifact owns each remaining proof requirement before close.

## Scope

- Keep the work inside the existing `backend/api/data.py` evidence snapshot contract and `frontend/src/components/data-layout` UI.
- Do not create a separate library, git submodule, or package for this phase; the logic is a small derivation from the existing close proof plan and has no reusable boundary yet.
- Do not use Figma Code Connect.
- Do not expose raw email bodies, raw attachment content, stable provider IDs, provider credentials, or database evidence strings.
- Preserve unrelated `.Jules` working tree changes.

## Implementation Plan

- [x] Add `diligence_close_artifact_review_queue` to the evidence snapshot response.
- [x] Derive queue entries from `diligence_close_proof_plan`, grouped by `required_proof_artifact`.
- [x] Include owner areas, proof counts, blocked/ready counts, highest severity, buyer reviewer role, review status, acceptance summary, next action, snapshot verification requirement, and write boundary.
- [x] Include the field in the canonical digest payload and backend fixture assertions.
- [x] Add a UI section between close decision summary and close proof plan.
- [x] Add frontend fixture, copied JSON, and visible rendering coverage.
- [x] Generate a FigJam diagram for the proof-plan-to-artifact-review flow without Code Connect.
- [x] Run backend tests, ruff, frontend tests, diff review, and Ponytail review.
- [x] Push the PR branch and update PR #895 with Phase 27 evidence.

## Acceptance Criteria

- The first queue item groups `acquisition-readiness-summary.json` under `executive diligence reviewer` with blocked status and critical severity.
- The queue groups `remediation-actions.json` into one artifact-level item even when it contains both high and medium proof requirements.
- Every queue entry has `provider_write_executed: false`.
- `canonical_payload_fields` includes `diligence_close_artifact_review_queue`.
- The copied evidence snapshot JSON includes the new queue.
- The UI renders the queue with artifact, reviewer role, review status, proof counts, owner areas, next action, and snapshot verification requirement.
- Local backend and frontend validations pass.

## Evidence

- Backend: `python3 -m pytest backend/tests/test_data_api.py -q` passed with 9 passed and 1 skipped.
- Backend style: `ruff check backend/api/data.py backend/tests/test_data_api.py` passed.
- Frontend: `npm test -- src/app/data/page.test.tsx` passed with 12 tests.
- Frontend style: `npm run lint -- src/components/data-layout/QualityCheckTab.tsx src/components/data-layout/types.ts src/app/data/page.test.tsx` passed.
- Figma/FigJam: https://www.figma.com/board/mjH0tpDIvz5kj44kL6354R?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=13a088da-bb84-46fa-b47e-9a2de963735a
- Ponytail review: Lean already. Ship.
- PR #895 body updated with Phase 27 evidence.
- Live PR state after first Phase 27 push: head `74706cd3239bf50945cf3a588979b17af11cd2a7`, mergeable `MERGEABLE`, merge state `BLOCKED` only by queued checks at verification time, unresolved review threads `0`.
