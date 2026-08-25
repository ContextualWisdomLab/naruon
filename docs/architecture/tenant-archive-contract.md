# Tenant Archive Contract (Slice 1)

## Overview

The tenant archive lets a customer exit or migrate a tenant without losing
provenance. Slice 1 covers the email/thread/task domain: an owner-scoped,
deterministic, versioned JSON bundle produced by
`POST /api/tenant-archive/export`, and a dedupe-safe import through
`POST /api/tenant-archive/import`. The service implementation lives in
`backend/services/tenant_archive_service.py`.

## Bundle format

```json
{
  "manifest": {
    "archive_kind": "naruon_tenant_archive",
    "schema_version": 1,
    "exported_at": "2026-08-25T00:00:00+00:00",
    "included_domains": ["emails", "ticket_tasks"],
    "excluded_domains": ["credentials", "llm_providers", "runner_tokens",
                         "embeddings", "attachment_binary_content",
                         "content_graph", "project_graph"],
    "source_scope": {
      "owner_user_id": "…",
      "organization_id": "…",
      "organization_scope_label": "…"
    },
    "counts": {"emails": N, "ticket_tasks": M, "attachment_references": K}
  },
  "records": {"emails": [...], "ticket_tasks": [...]}
}
```

- **Determinism.** Email records are ordered by `(date, id)` and ticket-task
  records by `(created_at, id)`. Two exports of unchanged data differ only in
  the `exported_at` stamp.
- **Versioning.** `schema_version` is an integer. Imports fail closed on any
  unknown or newer version with deterministic error code
  `archive_schema_unsupported` (HTTP 422).
- **Scope.** Export reads exactly one owner user + organization scope using the
  same SQL owner filters as every other private surface. Import re-scopes all
  records to the *signed session's* destination owner + organization; bundle
  identity claims are never trusted as authorization material. A bundle whose
  manifest `source_scope.organization_id` differs from the signed session's
  organization is rejected with `archive_scope_mismatch` (HTTP 403).

## Exclusions

- Credential-bearing tables are out of scope entirely: mailbox credentials
  (`EncryptedString` columns), LLM provider API keys, runner registration
  tokens.
- Embedding vectors are derived data; imports stage zero vectors so later
  slices can regenerate embeddings with the destination tenant's provider.
- Attachment binary content is not exported in slice 1. Each attachment is
  listed as metadata plus a stable reference
  `<message_id>#attachment-<ordinal>` so a later slice can extend the same
  schema version (or a successor) with payload transfer.

## Opaque identifiers and provenance

Sequential database primary keys never appear in payloads. Public identity is
carried by:

- emails: `message_id` / `thread_id` / `fingerprint`;
- ticket tasks: globally unique `task_uid`;
- task → email links: source `related_message_id` provenance, re-linked to the
  destination row at import time (dropped to unlinked if the referenced
  message is absent from both the bundle and the destination scope).

Timestamps (`created_at` / `updated_at`) are preserved as provenance.

## Idempotent import

Import matches duplicates on strong scoped signals — the owner-scoped unique
`(user_id, organization_id, message_id)` constraint (with the repo's
angle-bracket message-id normalization) plus the stored email fingerprint for
fingerprint-only collisions — and tasks on their unique `task_uid`.
Re-importing the same bundle therefore reports every record under
`skipped_duplicate` and creates no rows. Expected failures return fixed
`error_code` values (`archive_bundle_malformed`, HTTP 422) rather than
message-derived statuses.

Before any database write, import rejects duplicate email identities (including
the equivalent `message-id` forms `value` and `<value>`) and duplicate task
uids. Archive-controlled display fields are normalized through the same
markup-removal boundary used by email ingestion: sender, recipients, subject,
body, attachment filename, and task title cannot persist active HTML or NUL
characters. A value that becomes empty after this normalization is rejected.

## Test coverage

- `backend/tests/test_tenant_archive_service.py` — mocked-session unit tests
  (manifest contract, scoping, attachment refs, opaque-id preservation,
  re-import skip semantics, fail-closed validation).
- `backend/tests/test_tenant_archive_api.py` — real HMAC signed bearer-session
  API tests including deterministic error-code mapping.
- `backend/tests/test_tenant_archive_postgres.py` — `@pytest.mark.postgres`
  round trip against real PostgreSQL: export → wipe scope → import → assert
  preserved ids/provenance → second import reports all-skipped.
