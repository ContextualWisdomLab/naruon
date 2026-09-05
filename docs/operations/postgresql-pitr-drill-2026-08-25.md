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
  `archive_command=if test -e /wal_archive/%f; then cmp -s %p /wal_archive/%f; else t=/wal_archive/.%f.$$; cp %p "$t" && mv "$t" /wal_archive/%f; fi`.
- Base backup: `pg_basebackup -X stream` executed inside `db-primary` into a
  named volume mounted at `/base_backup`.
- Raw local logs were captured during the drill and summarized below; the
  committed repository keeps only the redacted evidence summary.

Verified evidence:

```text
ok: primary accepts SQL
ok: base backup completed
ok: pre-recovery target marker committed
Recovery target time (UTC): 2026-08-26 03:43:51.657456 +00
ok: WAL segment containing pre-recovery marker archived (000000010000000000000004)
ok: archived segment present in /wal_archive volume
ok: post-target marker WAL archived (000000010000000000000005)
Stopping db-primary to simulate loss of the source primary.
Restoring into a fresh instance targeting 2026-08-26 03:43:51.657456 +00 UTC.
ok: restored instance finished targeted recovery and promoted
ok: restored instance contains pre-recovery marker
ok: restored instance excludes post-target marker
ok: restored instance accepts writes after promotion
```

Re-target guarantee evidence:

The restore entrypoint is retarget-safe. The `restore_data` volume keeps a
stamp file recording the exact `RECOVERY_TARGET_TIME` the current data
directory was recovered to; starting `db-restore` with a different target
wipes the stale data directory and re-materializes from the base backup, and
an unchanged target reuses it as-is. A missing `RECOVERY_TARGET_TIME` fails
closed at Compose interpolation time (`:?`) and again inside the entrypoint.
The drill now runs a second restore against an earlier target (captured
strictly before the pre-marker commit) on the same volume and asserts the
included/excluded rows flip accordingly:

```text
Stopping the first restored instance to re-target recovery.
Restoring again from the same volume targeting 2026-08-26 03:43:49.773286 +00 UTC.
ok: second restore finished targeted recovery and promoted
ok: second restore excludes pre-recovery marker committed after the new target
ok: second restore excludes post-target marker
ok: second restore excludes the first restore's post-promotion write
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
- A second restore on the same `restore_data` volume against an earlier target
  force-recreates the restore container so Compose applies the new target,
  re-materialized the data directory from the base backup and flipped marker
  inclusion (pre-marker row absent), proving the overlay is retarget-safe
  instead of silently serving a previously applied recovery target.
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
