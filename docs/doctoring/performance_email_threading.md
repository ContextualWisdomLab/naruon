# Deterministic email-thread ordering and reply-scan fast path

## Decision

Naruon orders ranked thread heads and the messages loaded for each selected thread by the complete descending key `(email_records.date, email_records.id)`. The list API may pass that already-ordered sequence to `thread_reply_candidate(..., is_descending=True)` instead of allocating a reversed copy and sorting the same rows again.

The database identifier is a deterministic tie-breaker, not a statement about real-world message chronology. It is used only when persisted timestamps are equal. Reply-state comparison uses the same `(date, id)` key so page membership and reply classification cannot disagree solely because equal timestamps were encountered in a different iteration order.

## Correctness boundary

PostgreSQL does not guarantee result order without `ORDER BY`, and a limited result requires a sufficiently unique ordering if stable page membership matters. The thread-head window ordering and the outer limited query therefore both include `date DESC, id DESC`. The focused regression supplies equal-date heads from different threads and requires `limit=1` to return the higher-ID head; it also verifies equal-date sent/external reply ties in both the ordinary sort path and the trusted descending fast path.

Callers must use `is_descending=True` only when they possess the complete descending `(date, id)` contract. Unordered callers retain the helper's deterministic in-memory sort. The existing `is_chronological=True` path remains a separate ascending-input contract.

## Performance claim boundary

The optimization avoids the `sorted(...)` list allocation and O(N log N) in-memory sort from the list API's per-thread reply scan. The reply scan itself remains O(N). This does **not** claim that the whole HTTP request, SQL window query, or database execution is O(N), nor that PostgreSQL will always avoid a physical sort. PostgreSQL may satisfy an `ORDER BY` from a suitable B-tree index, and `EXPLAIN`/production query telemetry remain the authority for whether the deployed plan actually does so.

## Verification and operator next action

Before merging or releasing this behavior:

1. require the equal-date page-membership and reply-classification regressions to pass on the exact PR head;
2. require the complete repository CI, exact coverage/docstring, security, dependency, container, and review gates on that same head;
3. after deployment, inspect representative mailbox plans with `EXPLAIN (ANALYZE, BUFFERS)` and latency telemetry before claiming a user-visible throughput improvement;
4. if the planner shows an expensive sort at realistic scale, evaluate a tenant-scope-compatible B-tree index separately rather than weakening deterministic ordering.

Rollback is source-compatible: remove the trusted descending call-site flag and allow `thread_reply_candidate` to use its deterministic sort. Do not remove the SQL tie-breaker merely to reproduce predecessor behavior, because stable `LIMIT` membership is a correctness property.

## References (APA 7th)

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: 7.5. Sorting rows (ORDER BY).* https://www.postgresql.org/docs/18/queries-order.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: 7.6. LIMIT and OFFSET.* https://www.postgresql.org/docs/18/queries-limit.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: 11.4. Indexes and ORDER BY.* https://www.postgresql.org/docs/18/indexes-ordering.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: 14.1. Using EXPLAIN.* https://www.postgresql.org/docs/18/using-explain.html
