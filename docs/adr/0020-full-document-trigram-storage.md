# ADR-0020: Full-document trigram storage repair

**Status:** Proposed — storage correctness candidate; performance and protected integration remain unverified.
**Date:** 2026-09-05
**Decision owner:** Naruon maintainers
**Scope:** Naruon-owned PostgreSQL search expressions and migration history. RankWeave retains fusion and query-normalization ownership; no provider, external source, or domain truth is transferred.

## Context and constraints

A user can import or restore a long document whose content is valid under the archive contract yet fail before export or search. In the pending #1497 integration, the unchanged large cited-segment test failed when PostgreSQL updated `content_segments.safe_text_content`. The real migrated schema failed with SQLSTATE 54000, while an ORM-only schema had hidden the index limit. This is a storage finding, not evidence that provenance serialization is wrong.

The four whole-document indexes introduced by `0010_language_agnostic_search` cover email subject/body, attachment content, content segments, and project title/summary. A PostgreSQL 16.15 isolated probe with 32,768 bytes and 4,097 distinct trigrams failed for both GiST signature lengths 256 and 2024; the same complete value persisted under GIN. Upstream leaf compression retains a trigram array, so increasing the internal signature length does not cap the leaf value.

Requirements remain full-content persistence, unchanged normalization and exact similarity ordering, tenant scope, reversible application rollout without record loss, and measured page p95 at or below 20 ms. A successful storage test alone does not satisfy the latency requirement.

## Proposed decision

In the context of complete document import, restore, and search,
facing whole-document GiST leaf-size failures,
we decided for a forward GIN storage-repair candidate using installed PostgreSQL capabilities
and against truncation, larger GiST signatures, and an unvalidated similarity threshold,
to achieve full-content persistence without changing candidate scores or ownership,
accepting index rebuild cost and loss of GiST distance-order acceleration as unresolved rollout risks.

- Add `0020_search_trigram_storage` after `0019_email_read_state_repair`; retain the published `0010` source and revision identity.
- Replace only the four canonical search indexes with GIN using the same complete normalized expressions and existing names. Use structured Alembic index operations in one transaction; do not copy or update product records.
- Keep the SQL distance ordering, limit, score, joins, and owner predicates unchanged. GIN does not accelerate distance-only top-k queries. Do not describe this candidate as indexed kNN or declare equivalent performance.
- Downgrade retains the corrected indexes and all data. Recreating the known failing GiST indexes could prevent rollback after valid large records have been stored. Retirement or an index-strategy replacement needs its own reviewed forward migration.
- Schema/migration glue remains in the existing Alembic boundary. No Python computational core, new dependency, or duplicated RankWeave implementation is introduced.

## Alternatives and rejection reasons

| Alternative | Assessment |
|---|---|
| Increase `siglen` | Rejected: both tested values fail on the same input; internal signatures do not bound leaf arrays. |
| Truncate, hash, exclude, or shrink content | Rejected: loses searchable content, changes the contract, or conceals the failure. |
| Remove search indexes without replacement | Rejected: abandons existing index-supported operators. |
| Add a fixed similarity threshold for GIN | Rejected without a recall-preserving derivation; it can omit candidates and alter fusion ranks. |
| Chunked GiST or a separate search runtime | Deferred for measured design comparison: storage/chunk identity, cross-boundary matches, global exact ranking, and tenant isolation require explicit contracts. A prefix-only index is insufficient. |
| Full-content GIN, unchanged ranking SQL | Selected as a Draft correctness candidate, not approval to ship an unmeasured slow search path. |

## Risks, verification, and follow-up

The transactional rebuild can hold locks and require substantial storage. The deployment owner must estimate index size, profile build/lock duration on representative data, serialize the exact-head migration, and verify rollback before production application. Do not weaken locking or cancel a live migration to accelerate review.

Run real fresh and historical migrations, full-content inserts/updates across all four surfaces, tail-query score assertions, repeat upgrade, and retained-record downgrade/re-upgrade. Then integrate the prerequisite into the existing #1468 → #1427 → #1497 stack without force and rerun the original unchanged archive-size regression.

Before acceptance or release, compare query plans and end-to-end p95/CPU/memory with representative permitted data across all affected pages and locales. Include cold and steady-state requests, failures, all size classes, and simultaneous writers. Do not downsample away expensive cases or claim synthetic unit records as production performance evidence. If ranking is the bottleneck, develop the proven hot-path contract at its canonical owner, Rust-first, and consume an immutable release. This PR remains Draft while that gate or hosted checks/review are incomplete.

## References (APA 7th)

PostgreSQL Global Development Group. (n.d.). *pg_trgm—Support for similarity of text using trigram matching (PostgreSQL 16).* Retrieved September 5, 2026, from https://www.postgresql.org/docs/16/pgtrgm.html

PostgreSQL Global Development Group. (n.d.). *trgm_gist.c* [Source code, commit ad6ffe6a1ffddf19603b13633f054f3d66ef4277]. https://github.com/postgres/postgres/blob/ad6ffe6a1ffddf19603b13633f054f3d66ef4277/contrib/pg_trgm/trgm_gist.c#L107-L143

The live experiment and reproduction receipt belong in [doctoring](../doctoring/search_trigram_storage.md). This Proposed ADR neither changes external-owner maturity nor proves a protected merge or deployed behavior.
