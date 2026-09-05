# Bounded attachment parse-source contract

## Customer outcome

An email attachment between 20 MiB and 64 MiB is not rejected by a hidden
parser-only limit in the proposed ingestion change. This is not yet a released
capability. Recognition can still reject the source above the verified provider
limit; the complete admitted bytes must survive that rejection. The Data workspace reports
unsupported formats explicitly, so the next action is to add a reviewed parser
or use the original provider file rather than treating metadata as extracted
content.

## Contract

`MAX_ATTACHMENT_PARSE_SOURCE_BYTES` is 64 MiB, matching the authenticated email
import budget. The parser is fail-closed:

- supported text formats are parsed inline within the existing character bound;
- PDF bytes are retained only for bounded deferred NewsDOM recognition;
- unsupported binary formats return `unsupported_content_type`,
  `unsupported_binary`, and empty content;
- oversized source bytes return `parse_size_limit_exceeded` and empty content.

This preserves provenance without claiming that an unsupported file was parsed.
The quality surface exposes the parser key and status, not raw attachment bytes,
message IDs, attachment IDs, credentials, or customer payloads.

## Evidence and next action

The parser boundary is tested in
`backend/tests/test_attachment_parser.py`. The import transport is tested in
`backend/tests/test_email_import_service.py`. If a customer needs a currently
unsupported format, add a dedicated parser proposal with sandbox, dependency,
provenance, and exact-head regression evidence before changing the registry.

## 2026-09-05 owner-stack repair

The repair starts at #1469
`ed4bebeddf05ce1da0c76aca77448deef6254fbb` and normally merges #1427
`cb08b1c3ea2aba8844fc29ef703c34368cc55e47`. It inherits the existing dependency,
forward migration, complete-text search storage, and PDF admission proposals.
No migration is stamped around a failure, no legacy table is fabricated, and
no index or constraint is removed to make the source fit.

### Failure, cause, correction

| Observation | Cause and correction | Evidence boundary |
|---|---|---|
| Fresh #1469 migration failed in `0001_initial_control_plane.py` with `relation "emails" does not exist` | Inherit the existing database-owner repair through #1427, including forward read-state and search-storage revisions; do not duplicate a local schema workaround | The pre-merge migration log is RED before any attachment test runs |
| Actual 20 MiB + 1 byte document rejection logged a warning; attachment sibling already handled it as expected admission | `process_pending_document` lacked the `NewsdomPayloadTooLargeError` branch. Add the specific failure/INFO branch before general request errors, retaining bytes | Reproduced 1 failed / 62 passed; corrected 63 passed in the strict unit suite |
| New real-PDF test setup errored on `LocalPath.write_bytes` | Convert the existing pytest cache path to stdlib `Path` | Harness error, not a product RED or passing DB test |
| New real-PDF test referenced a nonexistent validation function | Use the actual `validate_newsdom_base_url_details_async` boundary, matching the existing client and unit tests | Harness error; test must subsequently reach real persistence and worker execution |

### Provider authority

Git refs rechecked at 2026-09-05 09:33 UTC:

- NewsDOM protected-source `develop` is
  `e06b1f3fb10903569124af011da213951e6e2473`; its `/parse` guard is 20 MiB.
- Proposed NewsDOM #665 head is
  `14eb886a91702074b4a0ae1b2fc21f84cec88d37`. A PR ref proves source identity,
  not merge state, deployment, or availability.
- Latest release metadata still names immutable `v0.2.0`; its tag resolves to
  `c26f3db7e9176b6e698b4e686aeda79b15a010b9`. The earlier source audit found
  unbounded `file.read()` there, not an immutable bounded 64 MiB API contract.

The Naruon guard stays 20 MiB. NewsDOM must provide its protected merge,
immutable bounded release, and compatibility evidence before Naruon pins and
adopts a larger contract. No deployed capacity is inferred from these refs.
API quota failures during the fresh PR/ADR inventory are unknown evidence, not
an empty PR set or proof that ADR-0023 is free.

### Real corpus and reproducibility

`backend/tests/test_attachment_source_postgres.py` reuses the existing isolated
`fresh_database_url` migration harness. It downloads only the fixed NASA HTTPS
URL with redirects and environment proxy inheritance disabled, bounds the read,
and checks length and SHA-256 before caching or using the book. A changed,
truncated, oversized, or unavailable corpus fails instead of silently replacing
it with synthetic content. Existing cached bytes are revalidated on every run.

- Source: NASA, *Earth at Night* (2019),
  <https://www.nasa.gov/wp-content/uploads/2019/11/earth_at_night_508.pdf>.
- Original length: **40,758,835 bytes**, PDF 1.7, **200 pages**, not encrypted.
- SHA-256: `8e622ca8f6d1ba0cf809549bddfee69e6754c3a3480d151c1fb54baf49b09be0`.
- The acknowledgments, printed p. xiv, state that the material is public domain
  and free to use. The book stays in the ignored pytest cache, not the Git tree.
- Neither truncation, repetition, compression changes, page removal, nor fake
  recognized output is used. Test-scope record identifiers are isolated technical
  identifiers, not customer identities.

Run from `backend` against an isolated PostgreSQL/pgvector test service with
ephemeral test credentials in `DATABASE_URL` and `AUTH_SESSION_HMAC_SECRET`:

```sh
uv sync --locked
uv run --frozen python scripts/migrate_db.py
uv run --frozen python scripts/migrate_db.py
uv run --frozen python -m pytest -q -W error -ra --tb=short \
  tests/test_attachment_source_postgres.py \
  tests/test_attachment_parser.py tests/test_newsdom_client.py \
  tests/test_newsdom_worker.py tests/test_email_import_service.py \
  tests/test_email_parser.py
```

Both attachment and workspace-document cases commit the original source, load
it in a new session, keep it pending without a provider, then commit the actual
client's pre-network size rejection. Fresh sessions compare every decoded byte,
status, and record identity. A flushed destructive content change is rolled
back, and another session must see the original source and failed status.
The migrated GIN attachment search index remains valid during the real writes.
This verifies retention, not successful PDF recognition, signed browser upload,
cross-tenant authorization, provider-network behavior, or a latency target.

Exact 20 MiB, 20 MiB + 1 byte, 64 MiB, and 64 MiB + 1 byte payloads are separately
exercised by the parser/client/worker **unit** tests. They use deterministic
synthetic bytes and are not presented as structurally valid real-PDF evidence.

### Combined local execution receipt

On 2026-09-05 the merged working tree passed **276 tests, 0 failures, 0 errors,
0 skips**, in **98.81 seconds**, with `-W error`. This combines the six files in
the command above with the inherited owner suite:

```text
tests/test_email_read_state_migration_postgres.py
tests/test_alembic_migrations.py
tests/test_bootstrap_db.py
tests/test_data_api.py
tests/test_legacy_document_scope_postgres.py
tests/test_workspace_document_migration.py
tests/test_container_dependency_pin_contract.py
tests/test_search.py
tests/test_search_postgres.py
tests/test_search_answer.py
tests/test_hybrid_retrieval_fusion.py
```

Fresh and repeated migrations reached `0020_search_trigram_storage` on isolated
PostgreSQL 16.15 / pgvector. The service retained read-only root, explicit tmpfs,
256 MiB shared memory, loopback-only port publication, and no-new-privileges.
Both container and test network were removed after the terminal-success run.
The two real-PDF cases took 34.864 s (attachment) and 15.693 s (document),
including their migration/transaction work; these are not endpoint latency
measurements. The corpus was not made smaller and the indexes remained enabled.
The JUnit artifact SHA-256 is
`19bc54cec6bdc308b816fe2814b1999a64e9a0d2a7e47b8707d1b74210800c2e`.
Source-file Ruff and staged/unstaged whitespace checks also passed. This receipt
is local integration evidence, not hosted Checks, approval, merge, or deployment.

### Preserved ADR lineage and remaining work

ADR-0021 is inherited from the PDF-upload owner. The attachment branch's entire
earlier ADR-0005 proposal is preserved in
[the historical snapshot](pdf_dom_proposal_history.md); moving that snapshot out
of the numbered ADR directory removes a duplicate identity without losing its
deferral rationale. The attachment proposal formerly numbered 0006 becomes
ADR-0023, **Proposed**, subject to a complete current open-PR identity check before
push. Neither rename makes a decision Accepted or a PR merged.

Keep #1469 Draft until its owner stack, current-head reviews/Checks, released
provider pin, and real capacity evidence are complete. Still required: actual
64 MiB PDF/provider recognition, realistic concurrent memory/storage/index and
latency measurements, tenant quotas, document-specific actionable error detail,
and a governed retry after provider upgrade. Full byte preservation alone does
not satisfy p95 ≤ 20 ms. The existing Python service is not a reason to choose
Python for a new hot path; profile and implement any required runtime change in
the canonical owner with contract-preserving Rust priority.

## Research traceability

The bounded transport and fail-closed error contract are aligned with HTTP
representation semantics (Fielding et al., 2022) and secure development
verification practices (Souppaya et al., 2022). See
[`ADR-0023`](../adr/0023-bounded-attachment-parse-source-contract.md).

Josefsson, S. (2006). *The Base16, Base32, and Base64 data encodings* (RFC 4648).
Internet Engineering Task Force. https://www.rfc-editor.org/rfc/rfc4648.html

National Aeronautics and Space Administration. (2019). *Earth at night*.
https://www.nasa.gov/ebooks/earth-at-night/

Encode OSS. (n.d.). *QuickStart: Streaming responses*. HTTPX.
https://www.python-httpx.org/quickstart/#streaming-responses

Context7 quota was exhausted and DeepWiki had no repository wiki during this
repair. Official HTTPX/RFC/NASA sources and exact Git refs were used instead;
neither unavailable tool is claimed as executed verification.
