# Import lease lifecycle repair

Status: Proposed; owner Naruon #1317. This is a repair supplement, not an
allocated or accepted ADR. No protected merge or deployment is established.

## Failure and prerequisite decision

At owner head `1b422f15e6e5f56be679f691c8ff925c9a420fb1`, two isolated
PostgreSQL runs stopped before pytest: revision `0011_email_read_state`
attempted `ALTER TABLE emails ADD COLUMN is_read` although the fresh baseline
created `email_records`. Both processes exited 1; neither is a lease RED/GREEN
receipt. Their task-only database and network were removed after failure.

Before a merge commit, the selected prerequisite is existing migration owner
#1503 `19d5860bc27e860acba940390f5792721cd99e5e`, which includes the declared
Starlette test-client dependency from #1565. A normal merge preserves both
histories and the complete #1317 runtime/semantic-import delta. Existing
migration identifiers, including #1317's ownership follow-up, must not be
deleted or renumbered merely to make the revision graph converge.

Rejected alternatives: ORM metadata bootstrap would conceal the installation
failure; copying an unmerged sibling migration file would lose ownership and
review lineage; changing the published revision independently would create a
second migration writer. The merge is a proposed dependency, not adoption of
an immutable service release. Hosted review and checks remain required.

## Lease investigation

The actual caller `backend/api/emails.py:import_email_files` resolves the
provider with the caller's database session before `import_email_uploads`.
Imports commit each item and may roll back failed writes. The original
dedicated lease connection preserved session locks across these commits but
needed a second pool slot. Actual import with pool capacity one reproduced
pool exhaustion. Two simultaneous provider lookups also occupy both slots of
a two-slot pool before either can obtain an extra lease connection. Increasing
the default pool would conceal that dependency, not remove it.

The candidate wrapper retains the caller's connection and binds a separate
import session to it with native `join_transaction_mode="control_fully"`.
This explicitly adopts the existing transaction and keeps the physical
connection across item commits; it does not mutate the active caller's bind
(SQLAlchemy authors, n.d.). The wrapper owns the rest of this request's DB
lifecycle and closes both sessions afterward. The API has no later DB work.
No dependency, pool, lease service, or reconnect retry is added.

Caller precondition: only settled/read-only work may precede import. Pending
new/dirty/deleted ORM state is rejected. This guard does not detect already
flushed, uncommitted writes or arbitrary raw SQL writes. Do not call this entry
point inside such an external unit of work. The verified production caller
performs provider lookup only; another caller needs explicit transaction
isolation before adoption.

The original acquisition caught only `Exception`, excluding cancellation;
release did not check its unlock result. The candidate catches `BaseException`
and invalidates uncertain acquisition/release before close. Release requires
an actual `True` from PostgreSQL. A strongly held cleanup task shields only
invalidation/close against repeated cancellation, then propagates cancellation.
Import/model work remains cancellable; no model time limit is introduced
(Python Software Foundation, n.d.). Ordinary pooled close does not itself
prove physical session termination (PostgreSQL Global Development Group, n.d.).

After genuine connection loss and rollback, a connection-local
`before_cursor_execute` listener rejects SQL if the DBAPI connection identity
differs from the acquired holder. This guards SQL execution, not replacement
socket creation. Cleanup removes the listener. Reconnection cannot restore a
session-level lease by assumption.

```mermaid
sequenceDiagram
    participant Api as Signed import API
    participant Db as Held database connection
    Api->>Db: Provider lookup; retain checkout
    Api->>Db: Acquire account/session advisory lock
    loop Source items
        Api->>Db: Parse, persist, commit on the same connection
    end
    alt Unlock confirmed
        Api->>Db: Unlock true; commit; close
    else Acquisition/release uncertain or cancelled
        Api->>Db: Invalidate physical connection; close
    end
```

## Related graph identity repair

Once the one-slot import could run, another account importing the same observed
Message-ID failed `uq_content_nodes_uid`. Mail duplicate lookup was scoped,
but the globally unique graph identities were not. Persisted body and
attachment source identifiers now include the existing SHA-256 account key
(user bytes, NUL separator, organization bytes); derived nodes/segments/edges
inherit that separation. The Message-ID and text remain intact. Existing rows
and identifiers are not rewritten, and unique constraints remain enabled.

The direct import, graph fallback, and scoped embedding-preparation callers
share `_parse_email_content_results`. Unpersisted embedding-only previews may
omit account scope. Dropping uniqueness or rewriting source Message-IDs was
rejected because either loses graph integrity or provenance.

## Migration reconciliation and preserved delta

`0020_merge_import_registry` is a no-DDL merge of retained
`0019_merge_read_state_ownership` and `0019_email_read_state_repair`. Use
Alembic's native `ScriptDirectory` instead of the single-use regex parser to
verify the multi-line merge graph. No existing revision identifiers are removed.
#1503 changes historical `0011` for fresh canonical/legacy tables and adds a
forward repair for already-stamped installations; do not call the inherited
historical file byte-for-byte immutable. Normal merge ancestry, existing source
IDs, and the complete #1317 feature delta remain preserved.

## Reproduction and local evidence

Use task-only PostgreSQL/pgvector, never a customer database: interruption
tests terminate only their captured task-owned backend PID. The local runner
used `pgvector/pgvector@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`,
loopback-only ports, generated disposable credentials, non-root UID/GID 999,
read-only filesystem, explicit writable tmpfs, `no-new-privileges`, and
256 MiB shared memory. Supply only the task `DATABASE_URL` and generated
test signing secret; never load an operator's entire environment file.

From `backend/`:

```sh
uv sync --locked
uv run --locked python scripts/migrate_db.py
uv run --locked python scripts/migrate_db.py
uv run --locked python -m pytest -q -W error -ra --tb=short \
  tests/test_email_import_lease_postgres.py \
  tests/test_email_import_service.py tests/test_emails_api.py
```

The PostgreSQL module checks the actual Alembic head and never skips database
unavailability. Test-only pool/wait bounds detect deadlocks, not model runtime
limits. Independent observers derive the account key separately and check
both lease contention during work and availability after cleanup.

Local receipts in task directory `naruon-import-lease-evidence.SfahhS`:

| Receipt | Result | Meaning |
| --- | --- | --- |
| `full_import_red.xml` | 3 failed, 1 passed | Actual bounded-pool/provider-lookup import failure. |
| `owner_graph_red.xml` | 3 failed, 1 passed | Cross-account `uq_content_nodes_uid` collision. |
| `import_interruption_red.xml` | 1 failed, 1 passed | Two SQL attempts after actual connection loss/rollback. |
| `repeated_cancel_red.xml` | 1 failed | Second cancellation interrupted discard and retained the lease. |
| `repeated_cancel_candidate.xml` | 70 passed | Lease lifecycle and existing import tests after cleanup repair. |
| `import_concurrent_api_candidate.xml` | 134 passed | Simultaneous same-owner/other-user/other-organization imports plus existing API suite. |
| `import_signed_api_candidate_v2.xml` | 135 passed | Adds actual signed backend API import and unsigned rejection on a one-slot database pool. |
| `import_owner_stack_candidate.xml` | 242 passed | Adds migration, workspace, read-state, legacy-scope, attachment, bootstrap, dependency and Data API regression tests. |

Each candidate run completed fresh and repeated migration to
`0020_merge_import_registry`. Terminal exit and task container/network cleanup
were checked. These are dirty candidate results, not exact committed-head or
hosted evidence. The earlier `lease_green` filename is misleading: that run
had 129 passes and two failures and is not GREEN evidence.

The additional signed-ASGI replay exercises real backend verification,
provider lookup, import, duplicate handling, and unsigned rejection. Only the
database location is replaced, not authentication/import implementations. Its
first collection failed because the existing signer was imported without the
`tests` package prefix; fixing that import needs no `PYTHONPATH` workaround.
The corrected run exited 0 with 135 passes in 1.61 seconds and removed its
task container/network. It does not exercise the browser cookie/proxy path.

## Remaining gates

Application CI/stacked-base activation belongs to
[#1562](https://github.com/ContextualWisdomLab/naruon/pull/1562).
Its patch at `bc91b36dec70c14e0cde526e2330638f5e0ce352` does not provision the
migrated PostgreSQL contract needed here and by #1503. The
[owner request](https://github.com/ContextualWisdomLab/naruon/pull/1562#issuecomment-5557877080)
records this shared prerequisite. Do not duplicate its workflow in #1317 or
weaken real integration tests into mocks/skips to manufacture green checks.

Still required before readiness: committed-head rerun, hosted checks,
qualifying independent review, predecessor-first integration, and the then-live
required gate set. These tests do not establish browser cookie/proxy behavior,
provider embeddings, deployed import/search visibility, historical customer-data
rollback/re-upgrade compatibility, all attachment formats, 100% edge/docstring
coverage, or p95 acceptance.

Required evidence includes actual cancellation after server acquisition,
failed/interrupted/unconfirmed release, independent replica contention while
work runs and availability after cleanup, persisted import commits/rollback,
and supported pool-capacity/concurrent-request behavior. Helper-only tests do
not establish complete import orchestration, source retention, live provider
behavior, signed HTTP behavior, or performance acceptance.

DeepWiki was used to locate the flow, but its single-transaction inference and
unconditional-finally cleanup guarantee do not match the exact owner source.
Context7 was quota-limited; official documentation and installed source are
the fallback, not a successful Context7 lookup. An independent review agent
failed its usage limit before review; no approval or clean review is claimed.

## References

PostgreSQL Global Development Group. (n.d.). *Explicit locking* (PostgreSQL 16
documentation). Retrieved September 6, 2026, from
https://www.postgresql.org/docs/16/explicit-locking.html

SQLAlchemy authors. (n.d.). *Session API* (SQLAlchemy 2.0 documentation).
Retrieved September 6, 2026, from
https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.join_transaction_mode

Python Software Foundation. (n.d.). *Coroutines and tasks* (Python 3.14
documentation). Retrieved September 6, 2026, from
https://docs.python.org/3/library/asyncio-task.html#shielding-from-cancellation

SQLAlchemy 2.0.51 is the tested dependency pin; the retrieved documentation
serves 2.0.52. A session-level PostgreSQL lock survives transaction rollback;
ordinary pooled connection close does not itself prove session termination.

## Observed-source replay boundary

`backend/tests/fixtures/observed_queue_question.eml` retains a short question
from a public PostgreSQL mailing-list message dated April 27, 2014:
https://www.postgresql.org/message-id/CANsFX049q7C_vJAtn2BSJy_4hQPu0%3DJNtv-Lyzb%3DgbZu-be30A%40mail.gmail.com.
The excerpt retains the actual count and pool/session question. Names,
addresses, message identifier and subject are anonymized; the UTC timestamp
uses the archive's displayed time. This is an attributed short excerpt in a
normalized replay envelope, not a redistributed complete message, customer
inbox, provider-connected import, or representative load/performance sample.
The application test compares persisted text with the checked-in source and
also verifies scope, read state, duplicate handling and physical lease cleanup.
