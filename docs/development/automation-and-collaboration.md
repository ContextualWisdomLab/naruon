# Development Automation and Collaboration

This document contains repository-internal delivery rules. It is intentionally separate from the customer and operator README.

## Scope

These rules apply to human contributors, coding agents, review agents, and repository automation working on Naruon. Live branch protection and organization rulesets remain authoritative. Detailed merge-gate semantics are maintained in [`merge-gate-policy.md`](merge-gate-policy.md).

## Research and standards basis

This procedure is a repository policy, not a claim that one study uniquely determines a delivery process. Its review, feedback, and secure-development choices are grounded in three complementary sources:

- NIST SSDF 1.1 treats protected source, review/analysis, provenance, vulnerability handling, and root-cause improvement as integrated secure-development practices. NIST published SSDF 1.2 as an **Initial Public Draft** in December 2025; until a final revision supersedes 1.1, this policy uses 1.1 as the stable normative baseline and treats the draft only as informative current work.
- Bacchelli and Bird's empirical study of modern code review found that review supports defect discovery as well as code understanding, knowledge transfer, team awareness, and alternative solutions. That supports preserving review context and resolving findings against the actual changed revision rather than treating review as a ceremonial approval count.
- Forsgren, Humble, and Kim synthesize empirical DevOps research around small batches, continuous integration, fast feedback, and recovery-oriented delivery. Those findings support narrow changes, independent safe lanes, automated verification, and causal repair instead of large unverified batches.

APA 7 references:

- Bacchelli, A., & Bird, C. (2013). Expectations, outcomes, and challenges of modern code review. *2013 35th International Conference on Software Engineering (ICSE)*, 712–721. https://doi.org/10.1109/ICSE.2013.6606617
- Forsgren, N., Humble, J., & Kim, G. (2018). *Accelerate: The science of lean software and DevOps: Building and scaling high performing technology organizations*. IT Revolution.
- Scarfone, K., Souppaya, M., & Dodson, D. (2022). *Secure Software Development Framework (SSDF) version 1.1: Recommendations for mitigating the risk of software vulnerabilities* (NIST Special Publication 800-218). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-218

## Delivery procedure

1. **Stepwise execution** — Dependent work uses explicit PR ancestry and does not land before its parent.
2. **TDD and domain boundaries** — Use test-driven development at the smallest useful unit and preserve bounded-context ownership.
3. **Complete API wiring** — A product slice is not complete while its public UI, API, persistence, or adapter path is knowingly disconnected.
4. **Concurrent-work safety** — Do not overwrite, dismiss, or silently absorb unfamiliar changes from another active writer.
5. **Real browser verification** — UI behavior must be checked in a browser for the changed flow.
6. **Strict failure handling** — Governed validation failures require root-cause repair or an explicit external blocker.
7. **Queue convergence** — Resolve valid work in dependency order and remove only demonstrably duplicate, superseded, or invalid work.

## Exact-head CI evidence

Merge evidence belongs to one immutable PR head SHA.

- Read the current head before evaluating checks or reviews.
- Required checks, security evidence, review evidence, and thread-resolution state must correspond to that same head.
- A success from an earlier commit, base branch, merge simulation, or sibling PR is not evidence for the current head.
- A new push invalidates predecessor-head evidence and starts a new evidence cycle.
- Queued, pending, requested, waiting, or in-progress checks are wait states, not successes and not automatically defects.
- Failed, cancelled, timed-out, action-required, unknown, or unverifiable required states fail closed.
- Review comments and requested changes must be resolved or superseded on the current diff.
- Before a merge action, re-read live rulesets, current head, required contexts, reviews, and unresolved threads.

Use [`merge-gate-policy.md`](merge-gate-policy.md) for the detailed evidence procedure.

## PR stacking

A stacked PR is a dependency graph, not a shortcut around the protected base.

1. Declare the immediate parent PR and base branch in the child PR description.
2. Keep each child limited to the delta above its declared parent.
3. Run required security and CI workflows on every PR base, including intermediate stacked bases.
4. Land or close the parent before the dependent child is considered for integration.
5. Never use a child's checks, reviews, or mergeability as evidence that its parent is safe.
6. After the parent lands, converge the child onto the live protected `develop` tip without rewriting unrelated history.
7. Re-run the complete exact-head evidence cycle for the new child head.
8. Reinspect the final diff for duplicated parent commits, obsolete compatibility code, and unrelated scope before integration.

Independent PRs may proceed in parallel when they do not share an uncoordinated writer surface or dependency edge.

## Repository writer boundary

Each branch and overlapping path set has one active writer at a time. Preserve unfamiliar concurrent changes until ownership and intent are established. Central `.github` governance and sibling CWL repositories remain separate ownership boundaries; cross-repository fixes belong in their owning repository and contract.

### Sibling integration boundary

Naruon is an ecosystem hub, but every sibling owns its implementation and release lifecycle.

- Naruon may add an adapter, generated client, event consumer, feature flag, or contract test for a published sibling contract.
- Naruon must not copy a sibling implementation, write directly to the sibling database, or depend on an unpinned mutable branch.
- A required sibling change is delivered in a separate PR in the owning repository, then consumed through a released package, API, event schema, or OCI digest.
- The Naruon core must start and report a clear degraded or disabled state when an optional sibling is unavailable.

### Customer-provider writer boundary

Repository write ownership is distinct from provider write authority. Mail, calendar, contact, and file writes require server-authoritative source selection, scoped credentials, explicit execution intent, capability checks, conflict evidence, and an auditable connector result. A browser or model proposal cannot self-authorize a provider mutation.

## Workflow operation boundary

Do not weaken branch protection, dismiss substantive reviews, synthesize approvals, or convert stale/predecessor evidence into current evidence. Waiting on one lane does not prevent independent safe work elsewhere.

## Failure and recovery

When a gate fails:

1. identify the exact head SHA and failing context;
2. obtain the failing log, annotation, or reproducible evidence;
3. map the failure to the smallest owned source surface;
4. add or update a regression test when applicable;
5. push the narrow fix to the same assigned branch; and
6. verify the new exact head without transferring predecessor evidence.

When the cause is outside the repository, record the external dependency and leave the local gate fail-closed rather than adding a workaround that weakens authority.

## Related documents

- [`merge-gate-policy.md`](merge-gate-policy.md)
- [`../../AGENTS.md`](../../AGENTS.md)
- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`../operations/source-of-truth-and-writeback-sovereignty.md`](../operations/source-of-truth-and-writeback-sovereignty.md)
- [`../operations/release-deployment-architecture.md`](../operations/release-deployment-architecture.md)
