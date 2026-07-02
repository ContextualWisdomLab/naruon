# Diligence Close Owner Handoff Queue

## Goal

Add a deterministic owner-area handoff queue to the redacted evidence snapshot so buyer-close remediation can be assigned by operating team, not only by data-room artifact.

## Scope

- Keep the work inside the existing `backend/api/data.py` evidence snapshot contract and `frontend/src/components/data-layout` UI.
- Do not create a separate library, git submodule, or package for this phase; the queue is a small deterministic aggregation over the existing close proof plan.
- Do not use Figma Code Connect.
- Do not expose raw email bodies, raw attachment content, stable provider IDs, provider credentials, or database evidence strings.
- Preserve unrelated `.Jules` working tree changes.

## Implementation Plan

- [ ] Add `diligence_close_owner_handoff_queue` to the evidence snapshot response.
- [ ] Derive queue entries from `diligence_close_proof_plan`, grouped by `owner_area`.
- [ ] Include related artifacts, proof counts, blocked/ready counts, highest severity, buyer reviewer roles, handoff status, acceptance summary, next action, snapshot verification requirement, and write boundary.
- [ ] Include the field in the canonical digest payload and backend fixture assertions.
- [ ] Add a UI section after the artifact review queue and before the detailed proof plan.
- [ ] Add frontend fixture, copied JSON, and visible rendering coverage.
- [ ] Generate a FigJam diagram for the proof-plan-to-owner-handoff flow without Code Connect.
- [ ] Run backend tests, ruff, frontend tests, frontend lint, diff review, and Ponytail review.
- [ ] Push the PR branch and update PR #895 with Phase 28 evidence.

## Acceptance Criteria

- The first owner handoff item is `attachment_parsing`, groups `remediation-actions.json`, has `proof_count: 2`, and remains blocked with high severity.
- `email_ingestion` is assigned to `executive diligence reviewer` because it owns the critical acquisition readiness proof.
- Every queue entry has `provider_write_executed: false`.
- `canonical_payload_fields` includes `diligence_close_owner_handoff_queue`.
- The copied evidence snapshot JSON includes the new owner handoff queue.
- The UI renders owner area, reviewer roles, related artifacts, handoff status, proof counts, next action, and snapshot verification requirement.
- Local backend and frontend validations pass.

## Evidence

- Pending.
