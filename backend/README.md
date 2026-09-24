# Backend

FastAPI service for email ingestion, search, AI summaries, calendar sync, and
threaded email APIs.

## Setup

```bash
python3 -m pip install -r requirements.txt
python3 scripts/migrate_db.py
python3 -m pytest -q
uvicorn main:app --reload
```

Set `DATABASE_URL` and `AUTH_SESSION_HMAC_SECRET` explicitly through `.env`,
Docker Compose, CI secrets, or the runtime environment. Backend settings read
environment variables first, then `.env`, `../.env`, and `~/.env`; this supports
running from `backend/`, the repository root, or a local operator env file
without adding code defaults. The backend still fails closed when either
required value is missing. The Docker image runs `scripts/start_backend.py`
before `uvicorn`, so missing runtime settings are reported as a concise startup
configuration error instead of an import-time traceback. Direct container runs
must inject only the required backend settings through `--env`, an orchestrator
secret, or a minimal Naruon-specific env file.

Outbound SMTP/IMAP/POP3 connector destinations fail closed unless the normalized
tenant host is listed in the matching `ALLOWED_*_HOSTS` setting and the port is
listed in the matching `ALLOWED_*_PORTS` setting. The defaults allow SMTP
submission ports `465,587`, IMAP TLS port `993`, and POP3 TLS port `995`, but
operators must explicitly allow each provider hostname.

Prometheus `/metrics` is disabled by default. Set
`ENABLE_PROMETHEUS_METRICS=true` only behind a trusted scrape path or reverse
proxy access policy.

OpenTelemetry now requires an explicit `cwl_telemetry.TelemetryConfig` passed to
`core.telemetry.setup_telemetry(app, config)` before the first request. The
configuration must carry the exact 40-character source revision and an HTTPS
Collector origin with a scoped token; the SDK validates these before creating
exporters. The backend no longer interprets `ENABLE_OTEL`,
`OTEL_EXPORTER_OTLP_ENDPOINT`, or `OTEL_EXPORTER_OTLP_INSECURE`. A typed config
has not yet been wired to a production credential registry or the image revision,
so the default app remains uninstrumented. The draft `telemetry` extra pins the
shared SDK commit for integration testing; the hashed Docker dependency set
needs a reviewed released wheel and checksum before deployment.

For local fixture imports, `OPENAI_API_KEY` is optional. When absent,
`import_fixtures.py` uses zero-vector embeddings so the local threading proof
path does not need network access.

## Threading endpoints

- `GET /api/emails` returns inbox items grouped by `thread_id` with `reply_count`.
- `GET /api/emails/{id}` returns message details including `thread_id`,
  `message_id`, `in_reply_to`, `references`, and `reply_to`.
- `GET /api/emails/thread/{thread_id}` returns the conversation oldest to newest.
- `POST /api/emails/send` accepts `in_reply_to` and `references` and returns
  either real send status or explicit simulation status.

## Calendar writeback endpoints

- `GET /api/calendar/writeback-sources` returns signed-session scoped opaque
  CalDAV source registry rows.
- `POST /api/calendar/writeback-intent` returns intent metadata by default.
  `execute_provider=true` dispatches `write_caldav` to the active outbound
  runner only after source ownership, write capability, and If-Match evidence
  are available; otherwise it fails closed without claiming provider success.

## Data workspace endpoints

- `GET /api/data/quality-surface` returns signed-session scoped repository,
  document, ingestion, embedding, quality, and connector evidence without raw
  provider secrets or message/thread identifiers.
- `POST /api/data/documents` stores a workspace document row under the signed
  `workspace_id` and returns an opaque `document_id`.
- `POST /api/data/documents/{document_id}/reparse`,
  `/embedding-regeneration-intent`, and `/hwp-conversion-intent` re-check the
  signed workspace scope, update document status, and return
  `provider_write_executed=false` until provider-backed execution is explicitly
  in scope.

## Schema migration, bootstrap, and backfill

`python3 scripts/migrate_db.py` applies the Alembic history under
`backend/alembic` and is the managed-environment schema path. The initial
baseline revision creates the `vector` extension, materializes the current model
metadata, and runs the same idempotent backfill SQL used by local bootstrap.

`python3 scripts/bootstrap_db.py` remains a local/dev compatibility path. It
creates the `vector` extension, runs `Base.metadata.create_all` for fresh local
databases, and applies idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
statements for the email owner key (`user_id`) and threading columns
(`thread_id`, `in_reply_to`, `references`, `reply_to`) plus the owner/thread
indexes. Existing email rows that predate threading should then be backfilled by
reprocessing imported `.eml` files or by assigning `thread_id` with
`services.threading_service.assign_thread_id` in chronological order.

For existing local databases, the bootstrap stamps null `emails.user_id` values
with `NARUON_IMPORT_USER_ID` or `default` so local rows remain visible through
the authenticated-user query scope. Before claiming production multi-user
safety, audit and backfill historical `emails.user_id` values against verified
mailbox owners.

## Warning classification

Backend evidence should be collected with warnings promoted to errors whenever
the slice is under active change:

```bash
PYTHONWARNINGS=error python3 -m pytest -q
```

Historical third-party dependency warnings should be isolated or filtered with
an explicit rationale before merge evidence is accepted:

- `starlette.formparsers` imports `multipart`, which emits a pending deprecation
  warning.
- Compiled SWIG metadata emits `__module__` deprecation warnings during import.

Threading code should not add new warnings. Treat any new application warning
or log output containing `Timeout`, `Fatal`, `Warn`, or `Denied` as a regression.
