# ADR-0003: PR checks, review fixes, and non-admin merge control

- Status: Accepted
- Date: 2026-08-11

## Decision

- PR and review feedback is handled on the current head. After each fix, local
  tests and the current-head GitHub Checks are re-evaluated; stale check results
  are not treated as evidence for a newer commit.
- The delivery loop repeats `review -> correction -> current-head checks ->
  review` until all actionable findings are resolved or explicitly superseded
  with evidence. The agent may perform each in-scope iteration autonomously.
- Actionable failed Checks may be diagnosed and fixed autonomously within the
  branch. Pending or queued work is a wait state, not a reason to invent a
  bypass.
- No condition receives a generic `Blocker` status. A failed check or review
  finding becomes a correction task; a pending external operation remains a
  wait state while other safe work continues.
- Merge may be scheduled through the repository's permitted merge-queue or
  auto-merge mechanism, or performed manually by the authorized agent/user
  after review and required Checks are satisfied. The same agent may complete
  that non-admin merge action; it must not claim administrator authority.
- No administrator merge, branch-protection bypass, human or third-party review
  dismissal, token disclosure, or forced merge is part of this workflow. The
  repository-approved central scheduler may clean up stale automated bot
  review state only after rechecking the current head; that cleanup is not a
  substitute for resolving an actionable finding.

## Consequences

Delivery evidence stays tied to the exact PR head, while human review and the
repository's normal protection rules retain authority over the final merge.
