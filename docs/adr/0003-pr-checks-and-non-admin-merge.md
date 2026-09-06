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

## References

- Enrico Fregnan, Fernando Petrulio, and Alberto Bacchelli, [“The evolution of
  the code during review: an investigation on review
  changes”](https://link.springer.com/article/10.1007/s10664-022-10205-7),
  *Empirical Software Engineering* (2022). The study examines how code changes
  evolve through review; this supports repeating review and focused validation
  after each corrective commit.
- Santiago Torres-Arias et al., [“in-toto: Providing farm-to-table guarantees
  for bits and bytes”](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias),
  *USENIX Security Symposium* (2019). The work models independent build and
  delivery actors and verifies supply-chain integrity end to end; this supports
  current-commit evidence, trusted workflow materialization, and no merge
  bypass. The mapping to this PR gate is an engineering inference.

The source PDFs are not bundled because redistribution rights were not
established; stable links and summaries are provided instead.
