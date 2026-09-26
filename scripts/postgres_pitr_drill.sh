#!/usr/bin/env bash
set -euo pipefail

ha_compose_file="${POSTGRES_HA_COMPOSE_FILE:-docker-compose.postgres-ha.yml}"
restore_compose_file="${POSTGRES_PITR_RESTORE_COMPOSE_FILE:-docker-compose.postgres-pitr-restore.yml}"
project_name="${COMPOSE_PROJECT_NAME:-naruon-postgres-pitr-drill}"
postgres_db="${POSTGRES_DB:-ai_email}"
postgres_user="${POSTGRES_USER:-postgres}"
primary_port="${POSTGRES_HA_PRIMARY_PORT:-55442}"
replica_port="${POSTGRES_HA_REPLICA_PORT:-55443}"
restore_port="${POSTGRES_PITR_RESTORE_PORT:-55444}"

export POSTGRES_DB="${postgres_db}"
export POSTGRES_USER="${postgres_user}"
export POSTGRES_HA_PRIMARY_PORT="${primary_port}"
export POSTGRES_HA_REPLICA_PORT="${replica_port}"
export POSTGRES_PITR_RESTORE_PORT="${restore_port}"

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "POSTGRES_PASSWORD must be set before running the PostgreSQL PITR drill." >&2
  exit 2
fi

for compose_file in "${ha_compose_file}" "${restore_compose_file}"; do
  if [ ! -f "${compose_file}" ]; then
    echo "Compose file not found: ${compose_file}" >&2
    exit 2
  fi
done

compose=(docker compose -p "${project_name}" -f "${ha_compose_file}")
full_compose=("${compose[@]}" -f "${restore_compose_file}")

cleanup() {
  local main_status=$?
  if [ "${POSTGRES_PITR_DRILL_KEEP_STACK:-0}" = "1" ]; then
    echo "Keeping PostgreSQL PITR drill stack: ${project_name}"
    return "${main_status}"
  fi
  # The restore overlay requires RECOVERY_TARGET_TIME even for teardown-only
  # compose commands; fall back to a placeholder when the drill failed before
  # exporting a real target so the stack still gets removed.
  export RECOVERY_TARGET_TIME="${RECOVERY_TARGET_TIME:-teardown-placeholder}"
  local cleanup_status=0
  if "${full_compose[@]}" down -v; then
    :
  else
    cleanup_status=$?
    echo "Failed to clean up PostgreSQL PITR drill stack: ${project_name}" >&2
  fi
  if [ "${main_status}" -ne 0 ]; then
    return "${main_status}"
  fi
  return "${cleanup_status}"
}
trap cleanup EXIT

sql_exec() {
  local service="$1"
  local sql="$2"
  local -a compose_cmd=("${compose[@]}")
  if [ "${service}" = "db-restore" ]; then
    compose_cmd=("${full_compose[@]}")
  fi
  "${compose_cmd[@]}" exec -T -e "PGPASSWORD=${POSTGRES_PASSWORD}" "${service}" \
    psql -v ON_ERROR_STOP=1 -U "${postgres_user}" -d "${postgres_db}" -Atqc "${sql}"
}

wait_for_sql_result() {
  local service="$1"
  local sql="$2"
  local expected="$3"
  local label="$4"
  local attempt
  local result

  for attempt in $(seq 1 90); do
    result="$(sql_exec "${service}" "${sql}" 2>/dev/null || true)"
    if [ "${result}" = "${expected}" ]; then
      echo "ok: ${label}"
      return 0
    fi
    sleep 1
  done

  echo "Timed out after ${attempt} attempts waiting for ${label}; last result: ${result:-<empty>}" >&2
  return 1
}

echo "Starting PostgreSQL PITR drill stack: ${project_name}"
"${compose[@]}" up -d db-primary

wait_for_sql_result "db-primary" "SELECT 1" "1" "primary accepts SQL"

echo "Taking physical base backup into the base_backup volume."
"${compose[@]}" exec -T db-primary bash -c '
  set -euo pipefail
  mkdir -p /base_backup
  chown postgres:postgres /base_backup
  chmod 700 /base_backup
  find /base_backup -mindepth 1 -delete
  gosu postgres pg_basebackup -D /base_backup -X stream -v >/dev/null
'
echo "ok: base backup completed"

sql_exec "db-primary" \
  "CREATE TABLE IF NOT EXISTS naruon_pitr_drill (drill_marker text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());"

before_marker="pitr_before_$(date -u +%Y%m%d%H%M%S)_$$"
# Capture a second recovery target strictly before the pre-marker commit (and
# strictly after table creation) so the retarget phase can prove that marker
# inclusion flips when the same restore volume is reused with a new target.
second_recovery_target_time="$(sql_exec "db-primary" \
  "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US') || ' +00';")"
sleep 0.2
sql_exec "db-primary" "INSERT INTO naruon_pitr_drill (drill_marker) VALUES ('${before_marker}');"
wait_for_sql_result "db-primary" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = '${before_marker}'" "1" \
  "pre-recovery target marker committed"

recovery_target_time="$(sql_exec "db-primary" \
  "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US') || ' +00';")"
echo "Recovery target time (UTC): ${recovery_target_time}"
export RECOVERY_TARGET_TIME="${recovery_target_time}"

marker_wal="$(sql_exec "db-primary" "SELECT pg_walfile_name(pg_current_wal_insert_lsn());")"
sql_exec "db-primary" "SELECT pg_switch_wal();" >/dev/null
sql_exec "db-primary" "SELECT pg_switch_wal();" >/dev/null
wait_for_sql_result "db-primary" \
  "SELECT COALESCE(last_archived_wal >= '${marker_wal}', false)::int FROM pg_stat_archiver" "1" \
  "WAL segment containing pre-recovery marker archived (${marker_wal})"
wait_for_sql_result "db-primary" \
  "SELECT COUNT(*) FROM pg_ls_dir('/wal_archive') WHERE pg_ls_dir = '${marker_wal}'" "1" \
  "archived segment present in /wal_archive volume"

sql_exec "db-primary" "INSERT INTO naruon_pitr_drill (drill_marker) VALUES ('pitr_after_target');"
post_target_wal="$(sql_exec "db-primary" "SELECT pg_walfile_name(pg_current_wal_insert_lsn());")"
sql_exec "db-primary" "SELECT pg_switch_wal();" >/dev/null
wait_for_sql_result "db-primary" \
  "SELECT COALESCE(last_archived_wal >= '${post_target_wal}', false)::int FROM pg_stat_archiver" "1" \
  "post-target marker WAL archived (${post_target_wal})"

echo "Stopping db-primary to simulate loss of the source primary."
"${compose[@]}" stop db-primary

echo "Restoring into a fresh instance targeting ${recovery_target_time} UTC."
"${full_compose[@]}" up -d db-restore

wait_for_sql_result "db-restore" \
  "SELECT CASE WHEN pg_is_in_recovery() THEN 0 ELSE 1 END" "1" \
  "restored instance finished targeted recovery and promoted"

wait_for_sql_result "db-restore" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = '${before_marker}'" "1" \
  "restored instance contains pre-recovery marker"
wait_for_sql_result "db-restore" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = 'pitr_after_target'" "0" \
  "restored instance excludes post-target marker"

sql_exec "db-restore" \
  "INSERT INTO naruon_pitr_drill (drill_marker) VALUES ('pitr_post_recovery_write');"
wait_for_sql_result "db-restore" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = 'pitr_post_recovery_write'" "1" \
  "restored instance accepts writes after promotion"

echo "Stopping the first restored instance to re-target recovery."
"${full_compose[@]}" stop db-restore

echo "Restoring again from the same volume targeting ${second_recovery_target_time} UTC."
export RECOVERY_TARGET_TIME="${second_recovery_target_time}"
"${full_compose[@]}" up -d db-restore

wait_for_sql_result "db-restore" \
  "SELECT CASE WHEN pg_is_in_recovery() THEN 0 ELSE 1 END" "1" \
  "second restore finished targeted recovery and promoted"
wait_for_sql_result "db-restore" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = '${before_marker}'" "0" \
  "second restore excludes pre-recovery marker committed after the new target"
wait_for_sql_result "db-restore" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = 'pitr_after_target'" "0" \
  "second restore excludes post-target marker"
wait_for_sql_result "db-restore" \
  "SELECT COUNT(*) FROM naruon_pitr_drill WHERE drill_marker = 'pitr_post_recovery_write'" "0" \
  "second restore excludes the first restore's post-promotion write"

echo "PITR validation complete; restored DSN: postgresql+asyncpg://${postgres_user}:<redacted>@127.0.0.1:${restore_port}/${postgres_db}"
