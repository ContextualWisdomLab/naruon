# Cloud Agent development environment

Use this when a Cloud Agent or a fresh Ubuntu workstation needs a running
Naruon control plane (FastAPI + Next.js + PostgreSQL 16/pgvector) without
Docker Compose.

## Next action

1. Confirm `.cursor/environment.json` is the environment source for the VM.
2. After `start.sh` exits, open http://127.0.0.1:3000 (frontend) and
   http://127.0.0.1:8000/ (backend health).
3. Mint a member HMAC session against the generated `AUTH_SESSION_HMAC_SECRET`
   in `~/.env`, then import `.eml` fixtures through
   `POST /api/emails/import-files`.
4. If Postgres is down, re-run `bash .cursor/start.sh` — do not edit secrets
   into SQL by hand.

## Install versus start

| Script | Lifetime | What to put here |
| --- | --- | --- |
| `.cursor/install.sh` | Durable, source-derived | `postgresql-16` + pgvector, hashed `requirements-hashes.txt`, `pnpm@11.5.3 --frozen-lockfile` |
| `.cursor/start.sh` | Every boot | Postgres cluster, per-VM `~/.env`, `ai_email` + `vector`, `alembic upgrade head` |
| `environment.json` terminals | Long-running | `scripts/start_backend.py` and `pnpm dev` |

`install.sh` must use `python -m pip install --require-hashes -r requirements-hashes.txt`.
Unhashed `requirements.txt` is not an acceptable Cloud Agent supply-chain path.

## Secret handling

`start.sh` writes `~/.env` only when the file is missing. Generated values use
`secrets.token_urlsafe(48)` for `AUTH_SESSION_HMAC_SECRET` and
`Fernet.generate_key()` for `ENCRYPTION_KEY`, matching
`validate_auth_session_hmac_secret_value`.

The `postgres` role secret is applied by
`backend/scripts/reconcile_local_postgres_role.py`:

- empty `DATABASE_URL` user secrets fail closed
- the secret is dollar-quoted on `psql` stdin
- the secret never appears in `psql -c` or process argv

Do not mount this `~/.env` as a Compose `env_file`. Compose interpolation still
resolves `NARUON_ENV_FILE` > `~/.env` > `./.env` without leaking the file into
the container environment wholesale.

## Schema contract on a fresh database

`0001_initial_control_plane` runs `Base.metadata.create_all`, so
`email_records.is_read` is present with `DEFAULT true` on a current model.
`0011_email_read_state` only touches the retired `emails` table and is a no-op
when that table is absent. `0019_email_record_read_state` follows the shared
`0018_email_send_rate_buckets` migration and adds or defaults `email_records.is_read`
on older databases that already have `email_records` but lack the column or its
server default.

## Import quota lock

Owner import serialization uses `pg_advisory_lock(hashtext(namespace), hashtext(owner_key))`.
PostgreSQL `text` cannot store a NUL octet, so the owner key is a SHA-256 hex
digest of `user_id + 0x00 + organization_id`, not the raw NUL-separated string
(PostgreSQL Global Development Group, n.d.).

## References

PostgreSQL Global Development Group. (n.d.). *Character set support*.
PostgreSQL Documentation. https://www.postgresql.org/docs/current/multibyte.html

PostgreSQL Global Development Group. (n.d.). *psql — PostgreSQL interactive
terminal*. PostgreSQL Documentation.
https://www.postgresql.org/docs/current/app-psql.html
