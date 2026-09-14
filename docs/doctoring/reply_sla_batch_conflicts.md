# Reply-SLA bounded conflict recovery

Status: **Proposed integration evidence**. Date: 2026-09-14. Canonical product owner: Naruon PR #1486. Source repair lineage: PR #1670.

## Problem and ownership

PR #1670 verified that the old repeated-conflict fallback could degrade from batched recovery into one SAVEPOINT/flush attempt per remaining task. That behavior lengthened the write transaction under contention and also exposed rollback hazards: failed pending inserts were already detached by SAVEPOINT rollback, while an outer rollback could expire selected Email rows before fallback reused them.

PR #1486 owns the same service surface together with workspace isolation and the physical-connection scheduler lease. The #1670 production algorithm has therefore been adopted in the #1486 owner lane rather than merged independently. The combined service retains #1486's opaque `workspace_id` authorization and one-query workspace-scoped source reload. `TicketTask` still lacks first-class `workspace_id`; issue #1673 owns that aggregate/schema change and this repair does not invent a route-local substitute.

## Current invariant

Ordinary escalation remains one batch path with no per-email SAVEPOINT. Conflict recovery uses at most `REPLY_SLA_MAX_BATCH_ATTEMPTS` batch SAVEPOINT/flush attempts. Each failed uniqueness batch performs one owner-scoped reconciliation read and retries only unresolved rows. The implementation never falls back to one SAVEPOINT per task.

If contention remains unresolved after the batch budget, the service rolls back the whole local transaction and raises `ReplySlaTaskConflict("reply_sla_batch_retry_exhausted", ...)`. A uniqueness race with no visible winner remains the stable `reply_sla_task_conflict` domain error. Driver-classified non-unique integrity failures are re-raised after rollback; classification uses PostgreSQL SQLSTATE or SQLite symbolic driver codes rather than localized exception text.

Before an outer rollback, selected Email primary keys are retained as primitives. If rollback expires or detaches the mapped rows, the service reloads them in one SELECT constrained by `user_id`, `organization_id`, **and `workspace_id`**, preserves the requested order, and fails closed with `reply_sla_source_email_unavailable` if any source was deleted or left the authorized workspace. The endpoint preserves the specific conflict code in its HTTP 409 envelope while keeping customer-safe prose independent of internal diagnostics.

## Successor-completeness evidence

#1486 already contained the #1670 production behavior in `backend/services/reply_sla_escalation_service.py` and the API conflict-code propagation in `backend/api/tasks.py`. The missing inheritance was the dedicated transaction-budget evidence. Commit `399809a22c860b02d150f0793db66645a28bd8ef` adds a workspace-aware successor suite at `backend/tests/test_reply_sla_transaction_budget.py` rather than copying #1670's organization-only fixture verbatim.

The suite uses a real SQLAlchemy Session and SQLite constraints behind an async-method bridge. It checks:

- ordinary batches create no per-mail SAVEPOINTs;
- 10- and 50-mail repeated-conflict cases stay within the configured batch-attempt budget and preserve task/result authority;
- exhausted contention rolls back local updates with no partial commit;
- non-unique integrity failures are not converted into duplicate races;
- outer rollback performs one workspace-scoped Email reload rather than implicit per-row I/O;
- source deletion, owner change, organization change, **and workspace change** fail closed;
- completed tasks remain completed;
- unresolved unique races keep their stable domain classification;
- SQLSTATE classification does not depend on error prose; and
- the Tasks API preserves the specific machine-readable Reply-SLA conflict code.

These are unit/integration-contract tests, not a production throughput benchmark and not evidence that total SQL statement count is constant in input size. They also do not replace the real async PostgreSQL qualification already required by #1486 for uniqueness races, rollback/no-partial-write behavior, migrations, and physical-lease behavior.

## Reproduction

From `backend` with repository-locked development dependencies:

```sh
uv sync --locked
uv run --locked python -m pytest -q -W error tests/test_reply_sla_transaction_budget.py
```

For owner integration, also run the existing Reply-SLA API/tracking and real PostgreSQL suites on the same unchanged exact head. Hosted PR checks, independent review, protected merge, immutable release, and deployed behavior remain separate gates. No result from #1670 or an older #1486 head transfers to a later source-changing commit.

## Risks and follow-up

Three batch attempts are a bounded contention policy, not an empirically optimal constant. Under sustained races, returning HTTP 409 is preferred to retaining write locks while retrying rows one by one. If production evidence shows unacceptable contention, change the policy only with measured PostgreSQL workload evidence and preserve the no-partial-write invariant.

The task aggregate remains organization-scoped until #1673 lands. Source Email reload is fully workspace-scoped, but task-level workspace provenance cannot be represented as an aggregate invariant yet. Keep that structural limitation visible rather than hiding it in endpoint predicates.

The scheduler connection-ownership decision and real PostgreSQL lease evidence remain in `docs/doctoring/reply_sla_physical_lease.md`. The canonical product/technical Gap ledger remains `docs/product-technical-gap-baseline.md` under PR #1602's single-writer lane.

## References (APA 7th)

SQLAlchemy authors. (n.d.). *Session basics: Rolling back*. SQLAlchemy 2.0 documentation. Retrieved September 14, 2026, from https://docs.sqlalchemy.org/en/20/orm/session_basics.html#rolling-back

SQLAlchemy authors. (n.d.). *Transactions and connection management: Using SAVEPOINT*. SQLAlchemy 2.0 documentation. Retrieved September 14, 2026, from https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint

PostgreSQL Global Development Group. (n.d.). *Error codes*. PostgreSQL documentation. Retrieved September 14, 2026, from https://www.postgresql.org/docs/current/errcodes-appendix.html
