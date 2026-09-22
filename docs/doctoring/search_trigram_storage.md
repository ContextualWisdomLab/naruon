# Whole-document search storage failure

## Evidence boundary

Observed 2026-09-05. Proposed Naruon storage repair; no protected merge,
deployment, latency acceptance, or signed-browser restore is claimed.
The owner branch starts at #1503
`19d5860bc27e860acba940390f5792721cd99e5e`. The implementing PR records the
tested source head/tree; the published `0010_language_agnostic_search` file
is unchanged. [ADR-0020](../adr/0020-full-document-trigram-storage.md) records
the decision, rejected alternatives, lock cost, and performance prerequisite.

## Failure and causal probe

The pending #1497 integration of `705d8ece2c97edc8575ea59766fd8f68bf4cdb82`
with #1427 `02366791b2a449b8b23b527dcc550996361c0f96` completed fresh and
repeated migrations after a local revision-graph repair. Its broader test run
then reported 1 failed / 288 passed: the unchanged
`test_export_counts_cited_segment_bytes_once` failed before export when storing
full segment content. That uncommitted integration result is not a PR-head pass.

An isolated PostgreSQL 16.15 probe confirmed all four migration-created search
indexes used GiST. A 32,768-byte document containing 4,097 distinct trigrams
produced the following results:

| Probe | SQLSTATE | Outcome |
|---|---|---|
| GiST, `siglen=256` | `54000` | Index row requires 12,304 bytes; maximum 8,191 |
| GiST, `siglen=2024` | `54000` | Same failure |
| GIN, complete text | `00000` | Insert succeeds; complete stored text equals input |

This rules out signature enlargement as a repair. The upstream leaf compression
path materializes the complete trigram array. The original 8 MiB-class archive
regression remains unchanged; the smaller diagnostic is additional causal
evidence, not a replacement acceptance case.

The new owner regression first failed on all four surfaces (4 failed,
4 deselected) at the expected index-size boundary. It exercises historical
small records, new high-entropy values, updates, exact tail-word similarity
`1.0`, full-value equality, repeat upgrade, and writes after downgrade followed
by re-upgrade. The corrected path must also retain a valid trigram index;
dropping all indexes is not an acceptable pass.

## Reproduction

Use a task-owned disposable PostgreSQL database with pgvector, pg_trgm, and
unaccent, a free loopback port, random test-only credentials, and isolated
resources. Never point this fixture at customer data: it creates and removes
separate test databases. From `backend/`, supply the test database URL and
bootstrap secret without printing them:

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
  tests/test_search_answer.py tests/test_hybrid_retrieval_fusion.py
```

The first complete repaired run returned 131 passed, zero failed/skipped.
The final run with the actual-index-presence assertion also returned 131
passed, zero failed/skipped, in 28.03 seconds. Tests using in-process API overrides are not proof
of browser cookie authentication, external embeddings, or deployed endpoints.
The high-entropy records are unit/regression inputs, not production performance
data. The unchanged ranking query has no GIN distance-order acceleration.

The pinned local image is
`pgvector/pgvector@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`.
Each run uses read-only root, no-new-privileges, 256 MiB shared memory and
temporary database storage. Its exit trap removes only its exact Compose
project; other containers and persistent volumes remain untouched.

## Retained diagnostic receipts

Local files under `/private/tmp/naruon-search-index-rca.VRmUrq` are not hosted
artifacts or deployment evidence. Their hashes permit checking the local record:

| Artifact | SHA-256 |
|---|---|
| `index_probe.sql` | `c3374657723b58bdb2bb92bc14cb6d86a0bc871541c4e644df9090499c0ad69f` |
| `index_probe.log` | `e49ec2d43fb1686ae242eebefc869ad243527fa3ef7cc48c793e6e9dcf1c4ed1` |
| `owner_red.xml` | `acf98ced8c477d8ee2c44914319161ad1605435640ece86d0ae0f69bbc8e6a89` |
| `owner_final.xml` | `27e2773571bd25cbd23f9b93038191c0cf2d6c63f70bad949d6f8773e60c4164` |
| `owner_final_migration.log` | `a91543007102a19ab62a85f51dc9b3e027bf58c6c6b1101e82e93b5f82b19b3f` |

Follow-up: measure representative search and migration costs, address the
resulting performance findings at the canonical owner, propagate without force
through #1468 → #1427 → #1497, and rerun the complete migrated restore suite.
Do not close a predecessor or promote any owner proposal to released evidence.
APA 7th primary-source citations are retained in ADR-0020. The number was
selected after checking all 160 open PR file lists on 2026-09-05, including
the second file page of #1287. ADR-0008 already belongs to #1418 and ADR-0019
appears in #1419; the abandoned local 0008 filename was never committed.
