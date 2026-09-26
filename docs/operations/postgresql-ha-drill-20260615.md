# PostgreSQL HA Drill Evidence - 2026-06-15

Command:

```bash
POSTGRES_PASSWORD='<operator-secret>' \
POSTGRES_HA_PRIMARY_PORT=55432 \
POSTGRES_HA_REPLICA_PORT=55433 \
POSTGRES_HA_PROMOTE_REPLICA=1 \
./scripts/postgres_ha_drill.sh
```

Environment:

- Compose provider: `docker compose` via local `podman-compose`.
- Primary host port override: `55432`.
- Replica host port override: `55433`.
- Project name: `naruon-postgres-ha-drill`.
- Raw local logs were captured during the drill and summarized below; the
  committed repository keeps only the redacted evidence summary.

Verified evidence:

```text
ok: primary accepts SQL
ok: replica is in recovery
ok: primary sees pg_stat_replication sender
ok: primary marker row exists
ok: replica replayed marker row
ok: replica has vector extension state
READONLY_DATABASE_URL=postgresql+asyncpg://postgres:<redacted>@db-replica:5432/ai_email
Primary DSN remains DATABASE_URL=postgresql+asyncpg://postgres:<redacted>@db-primary:5432/ai_email
Promoting db-replica for explicit failover drill.
server promoted
ok: replica promoted out of recovery
ok: promoted replica accepts writes
Failover validation complete; rebuild a fresh replica before reusing the stack.
```

Outcome:

- Streaming replication was initialized through `pg_basebackup`.
- The replica replayed a primary marker row.
- The replica preserved `vector` extension state.
- The backend read-only DSN boundary was recorded with redacted credentials.
- Manual promotion was verified and the promoted replica accepted writes.
- The drill stack was removed after the run.

Production boundary:

This drill validates the local primary/replica evaluation stack and manual
promotion path. Production HA still requires operator-owned monitoring,
alerting, and a decision on manual promotion versus an HA coordinator such as
Patroni or Repmgr; WAL archival and restore drills from archived WAL are now
exercised separately in `docs/operations/postgresql-pitr-drill-2026-08-25.md`.
