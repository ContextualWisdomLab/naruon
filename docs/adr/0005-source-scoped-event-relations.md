# ADR-0005: Source-scoped event relations

**Status:** Proposed
**Date:** 2026-09-27
**Decision owner:** Naruon maintainers
**Scope:** E1 Story 1.4 in [the platform plan](../planning/naruon-platform-plan.md).

## Context

Story 1.4 calls for automatic `enables`, `conflicts`, or `unrelated` judgments
between events, with evidence, confidence, and one-gesture correction. The
worked RSVP, lodging, and approval cases combine facts from different sources.

Neither existing edge store is a source-neutral event ledger.
`knowledge_graph_edges` require an email, and `project_graph_edges` require an
email-backed content segment; `project_graph_objects` also require an email.
The abandoned `email_thread_edges` table was removed in migration 0011.
Calendar conflict evaluation currently accepts a request's VEVENTs but does
not persist them.
The personal-reference work in #1785 gives live mail owner-scoped content
segments, including attachments, while keeping unknown and personal material
out of organization project views.

## Decision

1. Give each event an idempotent identity tied to its verified source and owner
   scope. Retain the source record and exact evidence locator. Ingestion must
   verify source ownership; a client-supplied source ID alone is not evidence.
   Represent email, attachment, calendar, task, and later plugin events through
   this common contract, adding adapters only when their source can be checked.
2. Store event relations separately from project-object edges. Each relation
   records both event IDs, the verdict, calibrated confidence when available,
   and the source evidence and features that support it. An `unrelated` verdict
   is recorded only for a pair actually evaluated; absence of an edge is not an
   unrelated verdict.
3. Keep owner, organization, workspace, and personal/context visibility in the
   event and relation scopes. Do not compare or expose events across those
   boundaries without the explicit consent bridge required by Epic 5. Unknown
   personal classification remains owner-only.
4. Retrieve plausible pairs before classifying them from shared entities,
   temporal fit, location, and explicit causal or dependency cues. Bound the
   candidate set and expose sparse or competing evidence without inventing a
   confidence score. A shared date or location alone never proves `enables`.
5. Correct a displayed edge in one gesture. Persist the actor, prior verdict,
   new verdict, evidence, and time in the same transaction. A human correction
   takes precedence over later automatic recomputation until explicitly reset.
   No relation verdict itself sends an RSVP, edits a calendar, or changes a
   confirmed commitment.

## Alternatives considered

### Reuse the email or project graph edge tables

Rejected because their required email-backed segment cannot represent a
CalDAV event or another independently sourced event. It would also make
personal events appear in project candidate views or invite cross-owner joins.

### Compare every event pair and treat missing edges as unrelated

Rejected because pair counts grow quadratically and unrelated pairs dominate.
An omitted pair also has no evaluated evidence or confidence.

### Extend the transient calendar conflict response only

Rejected as the Story 1.4 storage path: it cannot link approval, mail, task,
and lodging evidence or retain a user's correction.

## Consequences

- The event source contract and owner checks precede relation inference.
  Calendar evidence must be admitted from an authorized source before it can
  enter the ledger; the current request-only conflict evaluator remains valid.
- Relation reads, corrections, and recomputation need scoped database tests,
  including cross-owner, personal-to-organization, duplicate-ingest, and
  corrected-edge cases. A displayed edge needs source navigation and a direct
  correction action.
- Existing project and email graph tables stay intact. This ADR does not claim
  that Story 1.4 is implemented; its acceptance requires the source adapters,
  stored relations, correction path, and user-visible evidence to work together.

## Implementation state (2026-09-27)

Draft [#1788](https://github.com/ContextualWisdomLab/naruon/pull/1788) admits
owner-private iCalendar uploads and parsed mail attachments into the event
ledger. It stores cited time overlaps as unresolved `candidate` relations with
no numeric confidence; overlap alone does not prove a commitment conflict.
For an explicit `RELATED-TO;RELTYPE=DEPENDS-ON` UID, it stores a directional
`enables` relation when the referenced event is unambiguous in the
owner-visible scope and ends before the
dependent event starts. The correction audit records direction changes.
RFC 9253 defines `DEPENDS-ON` as a dependency in some manner; it does not alone
prove a finish-to-start schedule, so the implementation requires that additional
chronology before classifying the pair. The draft does not supply authenticated
CalDAV inbound sync, lodging or approval adapters, shared-entity classification,
or evaluated automatic `unrelated` verdicts. The existing CalDAV account sync
function still reports skipped work; the writeback registry is not inbound
source evidence. These remain Story 1.4 acceptance work, not merge evidence.
The independent [CalendarWeave core issue](https://github.com/ContextualWisdomLab/CalendarWeave/issues/2)
owns the reusable calendar resource contract. Its candidate core, store,
authorization, and standards work lives in an open draft PR stack while
CalendarWeave `main` still contains only the seed README. Naruon must consume a
released contract after verified parity; neither a draft branch nor the
writeback registry is a substitute for authenticated inbound source evidence.

## References

- Douglass, M. (2022). [*Support for iCalendar relationships* (RFC 9253)](https://www.rfc-editor.org/rfc/rfc9253.html). RFC Editor. https://doi.org/10.17487/RFC9253
- Li, R., Wang, Z., & Du, X. (2025). [Efficient document-level event relation
  extraction](https://aclanthology.org/2025.repl4nlp-1.7/). *Proceedings of
  RepL4NLP 2025*, 92–99. Candidate retrieval before classification addresses
  the unrelated-pair imbalance.
- Chen, M., Cao, Y., Deng, K., Li, M., Wang, K., Shao, J., & Zhang, Y. (2022).
  [ERGO: Event relational graph transformer for document-level event causality
  identification](https://aclanthology.org/2022.coling-1.185/). *Proceedings
  of COLING 2022*, 2118–2128. Pairwise evidence alone can miss graph context.
