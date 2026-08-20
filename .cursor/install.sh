#!/usr/bin/env bash
# Idempotent repository bootstrap for Naruon Cloud Agent environments.
#
# Prepares durable, source-derived state after checkout:
#   * system packages (PostgreSQL 16 + pgvector, Python venv/build tooling)
#   * the backend virtualenv + pinned Python requirements
#   * the frontend pnpm dependency tree
#
# Per-boot service startup (Postgres, schema migrations, dev secrets) lives in
# .cursor/start.sh so it re-runs on every VM boot, including builds.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> [install] system packages (postgresql-16, pgvector, python venv, build tools)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  postgresql-16 \
  postgresql-16-pgvector \
  postgresql-client-16 \
  python3.12-venv \
  python3.12-dev \
  build-essential

echo "==> [install] backend virtualenv + requirements"
cd "$REPO_ROOT/backend"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-hashes.txt

echo "==> [install] frontend dependencies (pnpm@11.5.3)"
cd "$REPO_ROOT/frontend"
corepack enable
corepack prepare pnpm@11.5.3 --activate
corepack pnpm@11.5.3 install --frozen-lockfile

echo "==> [install] done"