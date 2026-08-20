#!/usr/bin/env bash
# Per-boot runtime reconciliation for Naruon Cloud Agent environments.
#
# Runs on every VM start (idempotent): brings up the PostgreSQL cluster,
# materializes a local dev .env with generated secrets on first boot, ensures
# the app database + pgvector extension exist, and applies Alembic migrations.
#
# Dependency installation lives in .cursor/install.sh; this script only
# reconciles per-boot state and then returns so the backend/frontend terminals
# can start.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ENV_FILE="$HOME/.env"
PY="$REPO_ROOT/backend/.venv/bin/python"

echo "==> [start] ensuring PostgreSQL 16 cluster is online"
if ! pg_lsclusters -h 2>/dev/null | awk '{print $4}' | grep -q online; then
  sudo pg_ctlcluster 16 main start || true
fi
# Wait for the server to accept connections before touching it.
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then break; fi
  sleep 1
done
if ! sudo -u postgres pg_isready -q; then
  echo "==> [start] PostgreSQL did not become ready" >&2
  exit 1
fi

echo "==> [start] generating local dev .env on first boot (secrets are per-VM)"
if [ ! -f "$ENV_FILE" ]; then
  "$PY" - "$ENV_FILE" <<'PYGEN'
import os, secrets, sys
from pathlib import Path
from cryptography.fernet import Fernet

env_path = Path(sys.argv[1])
db_password = secrets.token_urlsafe(24)
hmac_secret = secrets.token_urlsafe(48)
enc_key = Fernet.generate_key().decode()

env_path.write_text(
    "# Naruon local dev environment (generated per-VM; not committed).\n"
    f"DATABASE_URL=postgresql+asyncpg://postgres:{db_password}@127.0.0.1:5432/ai_email\n"
    f"AUTH_SESSION_HMAC_SECRET={hmac_secret}\n"
    f"ENCRYPTION_KEY={enc_key}\n"
    "DEBUG=false\n"
    "RUNTIME_ENVIRONMENT=development\n"
    "ENABLE_PROMETHEUS_METRICS=false\n"
    "ALLOWED_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8000,http://127.0.0.1:8000\n"
    "SMTP_MODE=simulated\n"
    "OPENAI_API_KEY=\n"
    "OPENAI_EMBEDDING_MODEL=text-embedding-3-small\n"
    "OPENAI_MODEL=gpt-4o\n",
    encoding="utf-8",
)
os.chmod(env_path, 0o600)
print(f"wrote {env_path}")
PYGEN
fi

echo "==> [start] reconciling database role, database, and pgvector extension"
# Keep the local postgres role secret in sync with DATABASE_URL without
# interpolating it into SQL or the process argument list.
"$PY" "$REPO_ROOT/backend/scripts/reconcile_local_postgres_role.py" --env-file "$ENV_FILE"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='ai_email'" | grep -q 1; then
  sudo -u postgres createdb ai_email
fi
sudo -u postgres psql -d ai_email -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null

echo "==> [start] applying database migrations (alembic upgrade head)"
cd "$REPO_ROOT/backend"
"$PY" scripts/migrate_db.py

echo "==> [start] done"
