# Opaque UID backfill entropy contract

## Problem

Naruon uses opaque public identifiers such as `prompt_uid`, WebDAV `source_uid`, and project-folder `folder_uid`. Runtime ORM defaults already generate these identifiers from UUIDv4 values. The legacy PostgreSQL backfill paths, however, mixed `random()` and `clock_timestamp()` and then hashed the result with SHA-256.

The existing generated finding described this as Bandit B608 and as a direct cryptographic break. That diagnosis is not accurate. Bandit B608 is a hard-coded SQL-expression / SQL-injection heuristic; it is not a weak-random-number rule. The product issue is narrower: legacy/fresh-replay backfill generation used a weaker and inconsistent entropy source for public opaque identifiers than normal runtime creation.

## Decision

For backfills that create previously missing public UIDs, use PostgreSQL's native `gen_random_uuid()` as the random component while preserving the existing prefixes and SHA-256-derived output shape. This applies to:

- `prompt_templates.prompt_uid` in migration `0003_prompt_template_scope`;
- `webdav_accounts.source_uid` in bootstrap compatibility SQL;
- `project_folders.folder_uid` in bootstrap compatibility SQL.

The change is forward-looking for fresh installs, migration replay, and legacy rows whose UID is still null or empty. It must not rotate or rewrite already-populated public UIDs. Existing references, audit evidence, and external bookmarks may depend on those values remaining stable.

Opaque identifiers are defense in depth only. Tenant, organization, workspace, and object-level authorization remain the access-control authority; UUID unpredictability must never substitute for those checks.

## Compatibility and rejected alternatives

Naruon's PostgreSQL CI line supports native UUID generation, so this does not require a new extension contract. Keeping `random()` would preserve historical behavior but would retain the weaker, inconsistent entropy source. Changing the public format directly to raw UUID strings was rejected because it would alter the established identifier shape. Retroactive UID rotation was rejected because it can break referential and external identity continuity. Deterministic hashes of owner/title/path data were rejected because predictable input should not become the sole entropy source for opaque public identity.

## Verification boundary

`backend/tests/test_opaque_uid_backfill_entropy.py` locks both the bootstrap statements and the historical prompt migration source: all three UID backfills must use `gen_random_uuid()` and must not use `random()::text` as their random component. Real PostgreSQL migration/bootstrap execution remains required before merge; source-order assertions are not a substitute for hosted PostgreSQL acceptance.

## Traceability

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: UUID functions*. PostgreSQL Documentation. https://www.postgresql.org/docs/current/functions-uuid.html

PyCQA. (2026). *B608: hardcoded_sql_expressions*. Bandit documentation. https://bandit.readthedocs.io/en/latest/plugins/b608_hardcoded_sql_expressions.html
