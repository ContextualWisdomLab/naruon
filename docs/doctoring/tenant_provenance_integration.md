# Migrated tenant provenance integration

## Source and acceptance boundary

Proposed, observed 2026-09-05. The implementing #1497 PR records its exact
tested head and tree. No protected merge, immutable release, representative
search-performance acceptance, or signed browser restore is claimed here.

Remote #1497 started at `705d8ece2c97edc8575ea59766fd8f68bf4cdb82`.
The first normal integration checkpoint
`7ee6e68c31b2e716210fc8b62e287a78b765062b` preserved that history and #1427
`02366791b2a449b8b23b527dcc550996361c0f96`. Its actual migrated suite was
288 passed / 1 failed: the unchanged large cited-segment case exceeded the
GiST index-row limit. That checkpoint was not published as passing evidence.

The current integration then normally merges #1427
`cb08b1c3ea2aba8844fc29ef703c34368cc55e47`, inheriting #1572 search-schema
owner `cd8ff413d4ed8a5f2855c47a21a31db5661cd487` through #1468. No source
copy, force push, fake legacy table, revision stamping, index omission, or
smaller replacement of the original archive regression is used.

## Repairs and preserved behavior

- `0021_merge_provenance_workspace` joins `0018_provenance_identity` and
  `0020_search_trigram_storage`. The local checkpoint's not-yet-pushed merge
  revision was renamed before publication; inherited revision IDs stay intact.
- The unmerged provenance proposal's downgrade retains its identity mappings.
  A real rollback test first reproduced their destruction. Historical upgrades,
  already-stamped paths, retained records through downgrade, and re-upgrade
  exercise the actual migration graph.
- Forced-overlap transactions test identical retries and incompatible input.
  The latter must produce one successful import, one rejected writer, intact
  winning records, and no losing rows or mappings. The API success tests still
  use service overrides; they are not signed HTTP-to-database restore evidence.
- All four canonical search indexes remain present as GIN, with full-content
  insert/update and tail-word score assertions. The inherited search candidate
  preserves ranking SQL but does not supply GiST distance-order acceleration.
  Representative p95 and migration build/lock/storage costs remain open gates
  under [ADR-0020](../adr/0020-full-document-trigram-storage.md).
- [ADR-0022](../adr/0022-tenant-provenance-portability.md) retains the former
  ADR-0007 proposal and #1497 discussion lineage. An all-open-PR file inventory
  found another ADR-0007 in #1361. The PDF predecessor similarly preserves its
  former 0005 proposal as ADR-0021; none is prematurely Accepted.

## Reproduction

Use a task-owned disposable PostgreSQL database, never customer data. Reuse the
isolated image/resource contract in
[search storage doctoring](search_trigram_storage.md), supply random test-only
credentials without printing them, and run from `backend/`:

```sh
uv sync --locked
uv run --frozen python scripts/migrate_db.py
uv run --frozen python scripts/migrate_db.py
uv run --frozen python -m pytest -q -W error -ra --tb=short \
  tests/test_email_read_state_migration_postgres.py \
  tests/test_alembic_migrations.py tests/test_bootstrap_db.py \
  tests/test_data_api.py tests/test_legacy_document_scope_postgres.py \
  tests/test_workspace_document_migration.py \
  tests/test_container_dependency_pin_contract.py \
  tests/test_search.py tests/test_search_postgres.py \
  tests/test_search_answer.py tests/test_hybrid_retrieval_fusion.py \
  tests/test_tenant_provenance_bundle.py
```

The final terminal receipt is **345 passed, zero failed/skipped**, with
`-W error`, in 176.52 seconds. Fresh and repeated migration reach the single
`0021_merge_provenance_workspace` head. The unchanged
`test_export_counts_cited_segment_bytes_once` now passes, as do the retained
identity and forced incompatible-writer cases. The command and its exact
Compose cleanup both complete with exit zero. Ruff and 13 touched-document
file links also pass; no browser or performance pass is inferred.

Local artifacts are under `/private/tmp/naruon-search-index-rca.VRmUrq`; they
are not hosted artifacts. `prop1497_tests.xml` has SHA-256
`e17b09ba990b8d58a51dc00d4d7386474102e3b2996c65e9e79e07214e802eb5`;
`prop1497_migration.log` has SHA-256
`df9f68f8245cff79e8e3f5a86339787d8d2abdfacedd30a061be2a35b0fd0fb5`.
Generated test records are regression inputs, not representative production
performance data.

Historical release-note counts (`151 passed`, bootstrap `2 passed`, full
backend `1972 passed, 3 skipped`) describe earlier scoped runs. They did not
prove this combined migration graph and have been removed from customer-facing
release copy without deleting their historical record. BagIt 1.0, RO-Crate 1.3,
PROV, API authority, and the unchanged archive bounds remain specified in the
ADR and design contract, not exposed as implementation details in release copy.
