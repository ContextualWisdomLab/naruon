# PostgreSQL PITR Drill Evidence - 2026-08-25

Command:

```bash
POSTGRES_PASSWORD='<operator-secret>' \
./scripts/postgres_pitr_drill.sh
```

Environment:

- Compose provider: `docker compose` via local `podman-compose`
  (podman server 5.8.2).
- Compose files: `docker-compose.postgres-ha.yml` plus the
  `docker-compose.postgres-pitr-restore.yml` overlay for the `db-restore`
  target.
- Image: `pgvector/pgvector:pg16` (PostgreSQL 16).
- Primary host port override: `55442`.
- Replica host port override: `55443` (declared for parity; the PITR drill
  starts only `db-primary` and `db-restore`).
- Restored instance host port override: `55444`.
- Project name: `naruon-postgres-pitr-drill`.
- WAL archive: dedicated named volume mounted at `/wal_archive` on the primary
  with `archive_mode=on` and
  `archive_command=test -f /wal_archive/%f || cp %p /wal_archive/%f`.
- Base backup: `pg_basebackup -X stream` executed inside `db-primary` into a
  named volume mounted at `/base_backup`.
- Raw local logs were captured during the drill and summarized below; the
  committed repository keeps only the redacted evidence summary.

Verified evidence:

```text
ok: primary accepts SQL
ok: base backup completed
ok: pre-recovery target marker committed
Recovery target time (UTC): 2026-08-25 06:49:50.961210 +00
ok: WAL segment containing pre-recovery marker archived (000000010000000000000004)
ok: archived segment present in /wal_archive volume
ok: post-target marker WAL archived (000000010000000000000005)
Stopping db-primary to simulate loss of the source primary.
Restoring into a fresh instance targeting 2026-08-25 06:49:50.961210 +00 UTC.
ok: restored instance finished targeted recovery and promoted
ok: restored instance contains pre-recovery marker
ok: restored instance excludes post-target marker
ok: restored instance accepts writes after promotion
PITR validation complete; restored DSN: postgresql+asyncpg://postgres:<redacted>@127.0.0.1:55444/ai_email
```

Outcome:

- The primary archived WAL segments into the `/wal_archive` volume through
  `archive_mode=on`; `pg_stat_archiver.last_archived_wal` advanced past the
  segment holding the pre-target marker and the physical segment file was
  confirmed inside the volume.
- A physical base backup was taken after the marker-free starting point and
  before any drill markers were written.
- The pre-target marker row was committed strictly before the recorded
  `recovery_target_time`; the `pitr_after_target` row was committed after it.
- After simulating loss of the source primary, a fresh `db-restore` instance
  materialized the base backup with `recovery.signal`,
  `restore_command = 'cp /wal_archive/%f %p'`,
  `recovery_target_time`, and `recovery_target_action = 'promote'`.
- Targeted recovery replayed archived WAL, promoted out of recovery, contained
  the pre-target marker, excluded the post-target marker, and accepted new
  writes.
- The drill stack and volumes were removed after the run (`down -v`).
- The drill contract now emits `recovery_target_time` with an explicit numeric
  UTC offset (`+00`); a restore-server session `TimeZone` therefore cannot move
  the target implicitly. Cleanup errors are surfaced when the validation itself
  succeeds, so a reported success also proves that `down -v` completed.

Production boundary:

This drill validates WAL archival plus point-in-time restore against the local
evaluation stack only. Production still requires operator-owned archive
storage (durable, off-host retention), scheduled restore rehearsals with
monitoring/alerting around archiver failures, and an RPO/RTO decision for how
often base backups are taken.
