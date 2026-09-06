# Shared-send migrated PostgreSQL evidence

Status: Proposed; existing source owner [PR #1417](https://github.com/ContextualWisdomLab/naruon/pull/1417).
Local checks do not establish protected integration, delivery, or performance.

## Problem, dependency and preserved histories

Starting head `a9f334a442538b666e03e694731745d8aab4b45a` uses a PostgreSQL
transaction-scoped advisory lock, database clock, rolling 10-attempt/60-second
quota, and user/organization/workspace scope. However, its database smoke
creates ORM tables, reduces the quota to one and injects time. Its one-slot
pool regression uses a semaphore double. Neither proves the migrated runtime
or real pool/cancellation behavior.

Before committing, claim the existing owner and normally merge complete CI
prerequisite #1562 at `4d2e4abc2c369d5e85bced4027b6f81857721ea2`, including
#1503/#1565/#1571, rather than copy a runner or migration. This produced a real
fresh-install RED: Alembic reported two heads, `0018_security_audit_events`
and `0019_email_read_state_repair`. Preserve both histories with
`0020_merge_send_registry`, a no-DDL merge revision. Do not delete either parent,
stamp over missing work, switch the deployment target to a partial branch, or
claim an unreleased foundation is available. Only CHANGELOG had a textual merge
conflict; both entries were retained. Keep this PR Draft on the CI prerequisite.

Alembic's merge-node mechanism makes both parent paths prerequisites of one
head (Bayer, n.d.). The same runner now completes fresh and repeated upgrades.
This is repository-local stack integration, not permission to consume source
from an external service or bypass an immutable release contract.

## Behavioral checks and failure analysis

The updated database fixture reads the migrated audit table without creating
it. New tests use the production quota and database time: 80 concurrent attempts
across four scopes produce 10 allowed reservations and one durable quota event
per scope; the real 61-second wait verifies expiration without accelerating the
clock. Each dimension changes independently, so a missing user, organization or
workspace predicate cannot borrow another dimension's isolation.

A separate one-slot engine queues behind a real advisory lock. The test waits
until PostgreSQL observes that wait, cancels the task, verifies no checked-out
connection remains and confirms a subsequent attempt creates exactly one
reservation. Initial observation failed because PostgreSQL caches activity
snapshots within a transaction. Refreshing with `pg_stat_clear_snapshot()` fixes
the test observation without releasing the barrier lock; this was not a runtime
limiter defect (PostgreSQL Global Development Group, n.d.-b).

A real signed backend HTTP request reads persisted tenant configuration and
uses the same one-slot pool as the real limiter. Only DNS validation and SMTP
delivery are substituted at the external boundary. Removing the existing
request rollback temporarily makes this test fail with HTTP 503 and exhausted
pool capacity; restoring it recovers the existing behavior. No mutation is
retained. An initially invalid reserved recipient suffix was corrected in the
test fixture; validation was not weakened. This does not exercise the browser
cookie/proxy path, prove actual SMTP delivery, or measure customer latency.

Before final commit, the focused four-file run passed 74 tests in 62.09 seconds
with fresh/repeated migrations and completed test-only container/network cleanup.
The final PR receipt must name the unchanged committed head and JUnit digest.
Subsequent whole-suite execution must first inherit #1562's nested subprocess
isolation follow-up; the parent environment alone does not protect children
that replace it. Retain failed candidates separately from GREEN evidence.

Run after installing the existing hash-locked core and Noema requirements:

```sh
bash scripts/ci/run_backend_postgres.sh
```

Ponytail reuse keeps the existing limiter, transaction cleanup and CI lifecycle;
only migration reconciliation and missing behavior checks are added. No new
runtime package, generic abstraction, quota heuristic or model timeout is needed.
Remaining acceptance: current-head hosted checks and independent review, parent
integration, protected merge, delivery/browser evidence, and realistic load.
No coverage percentage, release, deployment or p95 claim is established here.

## References (APA 7)

Bayer, M. (n.d.). *Working with branches*. Alembic documentation. Retrieved
September 6, 2026, from https://alembic.sqlalchemy.org/en/latest/branches.html

PostgreSQL Global Development Group. (n.d.-a). *Explicit locking*.
PostgreSQL 16 documentation. Retrieved September 6, 2026, from
https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS

PostgreSQL Global Development Group. (n.d.-b). *The cumulative statistics system*.
PostgreSQL 16 documentation. Retrieved September 6, 2026, from
https://www.postgresql.org/docs/16/monitoring-stats.html
