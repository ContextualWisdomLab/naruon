# Development Automation and Collaboration

This document contains repository-internal delivery rules. It is intentionally separate from the customer and operator README.

## Scope

These rules apply to human contributors, coding agents, review agents, and repository automation working on Naruon. Live branch protection and organization rulesets remain authoritative. Detailed merge-gate semantics are maintained in [`merge-gate-policy.md`](merge-gate-policy.md).

## Phase 10 delivery procedure

1. **Stepwise execution** — Each dependent phase uses an atomic PR with explicit tracking, a pushed branch, and applicable review evidence. A dependent phase does not land before its parent phase.
2. **TDD and domain boundaries** — Use test-driven development at the smallest useful unit and preserve domain and context boundaries.
3. **Complete API wiring** — A product slice is not complete while its public UI, API, persistence, or adapter path is knowingly disconnected.
4. **Concurrent-work safety** — Do not overwrite, dismiss, or silently absorb unfamiliar changes from another active writer.
5. **Delegation** — Delegate independent, read-only investigation and bounded implementation work when that reduces shared-state contention.
6. **Real browser verification** — UI behavior must be checked in a browser for the changed flow.
7. **Strict failure handling** — `Timeout`, `Fatal`, `Warn`, and `Denied` output from governed validation is not clean evidence. Investigate and resolve the cause or record the external blocker.
8. **Queue convergence** — Resolve valid open work in dependency order and remove only work that is demonstrably duplicate, superseded, or invalid.

## Exact-head CI evidence

Merge evidence belongs to one immutable PR head SHA.

- Read the current `headRefOid` before evaluating checks or reviews.
- Required checks, security evidence, review evidence, and thread-resolution state must correspond to that same head.
- A success from an earlier commit, base branch, merge simulation, or sibling PR is not evidence for the current head.
- A new push invalidates predecessor-head evidence and starts a new evidence cycle.
- Queued, pending, requested, waiting, or in-progress checks are wait states, not successes and not automatically defects.
- Failed, cancelled, timed-out, action-required, unknown, or unverifiable required states fail closed.
- Conditional skipped jobs satisfy a gate only when the live ruleset and workflow contract explicitly make them non-required for that head.
- Review comments and requested changes must be resolved or superseded on the current diff.
- Before a merge action, re-read the live rulesets, current head, required contexts, reviews, and unresolved threads. Do not rely on remembered evidence.

Use the commands and robot-review contract in [`merge-gate-policy.md`](merge-gate-policy.md) for the detailed evidence procedure.

## PR stacking

A stacked PR is a dependency graph, not a shortcut around the protected base.

1. Declare the immediate parent PR and base branch in the child PR description.
2. Keep each child limited to the delta above its declared parent.
3. Run required security and CI workflows on every PR base, including intermediate stacked bases.
4. Land or close the parent before the dependent child is considered for integration.
5. Never use a child's checks, reviews, or mergeability as evidence that its parent is safe.
6. After the parent lands, retarget or rebase the child onto the live protected `develop` tip, resolve conflicts, and push the same child branch.
7. Re-run the complete exact-head evidence cycle for the rewritten child head.
8. Reinspect the final diff for duplicated parent commits, obsolete compatibility code, and unrelated scope before requesting integration.
9. Do not merge children out of dependency order or bypass a blocked parent with an equivalent hidden change.

Independent PRs may proceed in parallel when they do not share an uncoordinated writer surface or dependency edge.

## Repository writer boundary

Each branch and overlapping path set has one active writer at a time.

- A contributor or agent owns only the branch explicitly assigned to that work.
- Do not push to another contributor's PR branch, edit its commits, resolve its threads, or change its base without an explicit handoff.
- Review, analysis, and evidence gathering are read-only unless the branch owner requests implementation help.
- On handoff, record the current branch, head SHA, intended files, unresolved findings, and validation state before the new writer changes anything.
- If two changes overlap, serialize them, split the files or contracts, or create a declared stack. Do not race writes and repair the history afterward.
- Unknown files or commits are preserved until ownership and intent are established.
- Central `.github` governance and sibling CWL repositories are read-only dependencies from a Naruon PR unless that repository has a separately assigned writer and PR.

### Sibling integration boundary

Naruon is the ecosystem hub, but every sibling owns its implementation and release lifecycle.

- Naruon may add an adapter, generated client, event consumer, feature flag, or contract test for a published sibling contract.
- Naruon must not copy a sibling implementation, write directly to the sibling database, or depend on an unpinned mutable branch.
- A required sibling change is delivered in a separate PR in the owning repository, then consumed through a released package, API, event schema, or OCI digest.
- The Naruon core must start and report a clear degraded or disabled state when an optional sibling is unavailable.

### Customer-provider writer boundary

Repository write ownership is distinct from provider write authority. Mail, calendar, contact, and file writes require server-authoritative source selection, scoped credentials, explicit execution intent, capability checks, conflict evidence, and an auditable connector result. A browser or model proposal cannot self-authorize a provider mutation.

## Workflow operation boundary

Routine delivery must not manipulate GitHub Actions through a maintainer's personal account.

- Do not force-cancel queued or running workflows to free capacity.
- Do not manually rerun an entire workflow or failed jobs merely to seek a different result.
- Prefer the natural trigger created by the relevant code push, review event, scheduled controller, or approved bot-owned workflow contract.
- When a run is waiting, continue independent non-conflicting work or record the external wait state; do not convert waiting into artificial evidence.
- A genuine infrastructure failure may be retried only through the repository's authorized automation path and documented policy, never as an unexplained personal-account intervention.
- Do not use admin merge, branch-protection bypass, review dismissal, required-check suppression, or temporary policy weakening for routine delivery.

Creating or updating the code under review may naturally start new checks. That is different from cancelling or replaying an existing run.

## Review and merge responsibilities

- Review agents inspect and report; they do not silently become branch writers.
- Repair agents modify only the explicitly assigned branch and scope.
- Metadata controllers may publish idempotent status or blocker information within their documented permissions.
- Merge automation acts only after the live protected-branch contract is satisfied.
- The author of a change does not manufacture independent approval evidence.

## Failure and recovery

When a gate fails:

1. identify the exact head SHA and failing context;
2. obtain the failing log, annotation, or reproducible local evidence;
3. map the failure to the smallest owned source surface;
4. add or update a regression test when applicable;
5. push the narrow fix to the same assigned branch;
6. let the new head trigger its own evidence cycle; and
7. verify that no stacked child or concurrent branch was silently invalidated.

When the cause is outside the repository, record the external dependency, current head, observed state, and next non-destructive action. Do not report a waiting or unavailable external service as a passing gate.

## Related documents

- [`merge-gate-policy.md`](merge-gate-policy.md)
- [`../../AGENTS.md`](../../AGENTS.md)
- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`../operations/source-of-truth-and-writeback-sovereignty.md`](../operations/source-of-truth-and-writeback-sovereignty.md)
- [`../operations/release-deployment-architecture.md`](../operations/release-deployment-architecture.md)
