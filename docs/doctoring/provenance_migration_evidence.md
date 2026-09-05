# Provenance restore and migration evidence

## Status and customer consequence

Proposed; observed 2026-09-05. No protected merge, release, or live customer
restore is claimed. A customer must be able to install Naruon before importing
portable evidence. Passing import tests against ORM-created tables did not
establish that prerequisite: the actual fresh installation failed first.

## Exact revisions and observations

| Lane | Full source head | Observation |
| --- | --- | --- |
| #1497 provenance | `705d8ece2c97edc8575ea59766fd8f68bf4cdb82` | 224 PostgreSQL-backed suite tests passed, zero skipped; strict `-W error` rerun also passed. Fresh Alembic upgrade failed, exit 1. |
| #1502 CI proposal | `0b9e324a91fd2148b2b2759cca875ac7d50c86a0` | Fresh and repeat upgrades reached `0017_merge_newsdom_carddav_heads`; 64 focused tests passed in the existing local environment. Not clean-lock or stamped-forward-repair evidence. |
| #1503 before integration | `9c1851336fa04bcdc77c1c6e531afdb882583af1` | 73 tests passed with a retained, undeclared httpx2 package. Exact synchronization removed it; strict Data API collection then failed, exit 4. |
| #1565 dependency owner | `52dfc863d1a5d6e4e80b6366f719dd09f2aa6172` | Existing declared httpx2 dependency, lock, warning-suppression removal, and runtime regression delta; reused unchanged. |
| #1503 integrated owner | `19d5860bc27e860acba940390f5792721cd99e5e` | Tree `793aadd78a7ad2d6033ca6e12a931dfa776b7374`: exact synchronization, fresh/repeat upgrade to `0019_email_read_state_repair`, 75 tests with `-W error`, Ruff and diff checks passed. |

The #1503 commit has the before-integration and #1565 heads as its two parents;
neither history was rewritten. The verified pre-commit tree exactly matches
the committed tree. Its direct PR base is #1565, not protected `develop`.

## Root cause and rejected shortcuts

At #1497, `backend/tests/test_tenant_provenance_bundle.py` prepares tables using
`Base.metadata.create_all()`. That exercises the current models but does not
traverse the Alembic revision graph. Actual `scripts/migrate_db.py` execution
stops in `backend/alembic/versions/0011_email_read_state.py`:

```text
asyncpg.exceptions.UndefinedTableError: relation "emails" does not exist
ALTER TABLE emails ADD COLUMN is_read BOOLEAN DEFAULT true NOT NULL
```

The current table is `email_records`. Creating a fake `emails` table, stamping
past the failed revision, suppressing the exception, or copying a repair into
the provenance service would conceal the installation defect. Existing #1503
owns both the guarded historical path and forward
`0019_email_read_state_repair` for already-stamped databases. Editing an applied
revision alone cannot cause Alembic to replay it.

A second verification defect came from local package state. `uv run --frozen`
retained `httpx2==2.5.0` even though #1503 did not declare it. Exact
`uv sync --locked` in that task-owned worktree removed the extra package.
Strict TestClient collection then produced `ModuleNotFoundError: No module
named 'httpx2'` and Starlette's deprecation warning. Reusing #1565 fixed the
declared dependency; reinstalling it manually would have hidden the same gap.
`PYTHONWARNINGS=error` alone also does not neutralize pytest ignore rules.
Explicit `-W error` is used for the repaired receipt; marks and intentional
warning-catching test contexts still need review.

## Verification procedure and scope

Each database run used its own Compose project, a free `127.0.0.1` host port,
random test-only credentials, read-only root filesystem, no-new-privileges,
256 MiB shared memory, and tmpfs database storage. The installed image was
`pgvector/pgvector@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`
(PostgreSQL 16.15, aarch64). Each exact project was removed by its exit trap;
pre-existing services and persistent volumes were not changed. Credential
values were not printed or committed. Logs and the Compose input remain local
under `/private/tmp/naruon-provenance-pg.5wO5pq`; that path is not a hosted artifact.

From the integrated #1503 `backend/` directory, with the disposable database
URL and fresh bootstrap secret supplied only for the test process:

```sh
uv sync --locked
uv run --frozen python scripts/migrate_db.py
uv run --frozen python scripts/migrate_db.py
uv run --frozen python -m pytest -q -W error -ra --tb=short \
  tests/test_alembic_migrations.py tests/test_bootstrap_db.py \
  tests/test_data_api.py tests/test_email_read_state_migration_postgres.py \
  tests/test_legacy_document_scope_postgres.py \
  tests/test_workspace_document_migration.py \
  tests/test_container_dependency_pin_contract.py
```

Both migration commands exited zero; a read-only `SELECT version_num FROM
alembic_version` returned `0019_email_read_state_repair`. The suite returned
75 passed, zero failed/skipped. Historical read-state repair, pre-registry
installation, already-stamped repair, document scope, and data-preserving
downgrade paths run actual PostgreSQL; fast API tests remain mocked where their
fixtures say so. This is local source-tree evidence, not hosted gate evidence.

On #1497, the provenance and Data API command is:

```sh
uv run --frozen python -m pytest -q -W error -ra --tb=short \
  tests/test_tenant_provenance_bundle.py tests/test_data_api.py
```

That run passed 224 tests in 12.53 seconds, zero skipped, with real database
service tests. Its environment retained other packages outside the lock, so
do not promote it to clean-lock proof. API success tests replace the service;
they do not prove signed HTTP-to-database restore. Concurrent successful imports
are covered, but forced overlap of incompatible imports still needs evidence
of one rejected writer, intact winning content, and no losing rows or mappings.

## Dependency decision and next actions

1. Keep #1503 on #1565 and Draft until current-head hosted gates and qualifying
   independent review pass. This supersedes the historical
   [#1502-before-#1503 proposal](https://github.com/ContextualWisdomLab/naruon/pull/1503#issuecomment-5503791028);
   it does not create reciprocal prerequisites or close either PR.
2. Non-force propagate #1503 through #1468, #1427, then #1497. Preserve #1468's
   unique fixture/assertion delta. Reconcile the provenance lane's optional
   bootstrap statements with the owner's structured conditional index creation;
   do not replace whole files or discard tests to resolve overlap.
3. Integrating #1497 adds `0018_provenance_identity` alongside the owner's
   `0019_email_read_state_repair`. Join those heads with a forward merge revision
   and run the combined graph, fresh and historical paths, before claiming an
   installable restore. Neither published revision ID should be rewritten.
4. #1502 remains the CI-service lane on #1562, whose own parent is #1531.
   Integrate the existing #1503 forward repair by ancestry rather than copying
   `0019` to answer its [already-stamped database finding](https://github.com/ContextualWisdomLab/naruon/pull/1502#discussion_r3939592974).
5. AGENTS.md recurrence rules are owned by #1566
   (`5dade0a897c8f4ecd46a86e4f31ff61885e05a9b`), not repeated in product PRs.
   Current queued checks are wait states; neither a local pass nor PR metadata
   promotes Proposed work to a released or protected contract.

## Retained local artifact integrity

Hashes identify local receipts; they do not substitute for hosted retention.

| File under the local evidence directory | SHA-256 |
| --- | --- |
| `migration_fresh.log` (#1497 failure) | `2091d0064e3c341bf702a72cd7dc24763389b4127ff130419771e2ff7c728993` |
| `strict_provenance_test_results.xml` | `984b7de41a23f381ac6590daeedd8f09e4088fda4ab7e98601eca214d6982ba2` |
| `clean_lock_owner_testclient.log` | `91e82b377204c42bda20f6789a08230a7119ab6ed9e753dbbc8f4d83a229cd8c` |
| `integrated_migration_fresh.log` | `af944edcbac788fa25e2038e7716b435526e4227a6c3afeaba7ac1c1fdaf567d` |
| `integrated_owner_test_results.xml` | `d8fd58d035a40e19ab977122c21011f49df93b0527ba8d08fac34297197269a9` |

## References (APA 7th)

Alembic developers. (n.d.). *Tutorial*. Retrieved September 5, 2026, from https://alembic.sqlalchemy.org/en/latest/tutorial.html

Astral. (n.d.). *Locking and syncing*. Retrieved September 5, 2026, from https://docs.astral.sh/uv/concepts/projects/sync/

Docker, Inc. (n.d.). *Define services in Docker Compose*. Retrieved September 5, 2026, from https://docs.docker.com/reference/compose-file/services/

Docker, Inc. (n.d.). *Port publishing and mapping*. Retrieved September 5, 2026, from https://docs.docker.com/engine/network/port-publishing/

pytest developers. (n.d.). *How to capture warnings*. Retrieved September 5, 2026, from https://docs.pytest.org/en/stable/how-to/capture-warnings.html
