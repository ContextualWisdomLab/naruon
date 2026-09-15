# Fixture import attachment-enrichment invariant

Date: 2026-09-16
Status: Proposed repair for #1697

## Problem

The root fixture importer built an `Attachment` only after embedding generation succeeded. When enrichment failed, the exception path logged the failure and then committed the enclosing `Email` without the attachment. A derived vector was therefore acting as an accidental persistence prerequisite for source content.

The importer also reused one SQLAlchemy session across fixture files. Its duplicate-check `SELECT` starts an implicit transaction, so remote/model embedding must not run until that read transaction has been explicitly ended. Moving the duplicate check after enrichment would avoid an idle transaction but would also waste provider work for already imported fixtures.

## Invariant

Parsed source content is authoritative for fixture persistence. Embedding is derived enrichment.

- Check owner-scoped `message_id` duplication before enrichment. End that read transaction with `rollback()` before any body or attachment embedding call.
- A duplicate fixture returns without invoking enrichment and without leaving an open transaction for the next fixture.
- A parsed attachment remains attached to the Email aggregate when embedding generation fails; its `embedding` is nullable and may be `None`.
- Body embedding remains required by the current importer contract; if it fails, the email is not imported.
- After enrichment, re-check the duplicate guard because another importer may have written during the external-I/O window. From that re-check through thread lookup and commit, only database work remains.
- A database commit failure rolls the aggregate back and returns failure.

This is intentionally scoped to `backend/import_fixtures.py`; it does not redefine the separate production import service contract.

## Verification

`backend/tests/test_import_fixture_attachment_integrity.py` covers the causal ordering with a recording session: attachment enrichment failure preserves the original filename/content, all enrichment occurs after the initial duplicate-read transaction is released, and duplicate fixtures invoke neither enrichment nor thread lookup.

The same file now also contains a `@pytest.mark.postgres` acceptance path. Against the real pgvector-backed SQLAlchemy schema it imports an Email whose attachment embedding deliberately fails, reloads the aggregate with `selectinload`, and requires the persisted attachment to retain its original filename/content with `embedding=None`. It then deletes the Email and verifies that the related `email_attachments` row is removed through the model relationship cascade. Unique message/attachment identifiers isolate the smoke row from concurrent tests.

Existing fixture-import test doubles implement the rollback operation required by the real session protocol so they continue to exercise the same transaction boundary rather than bypassing it.

The PostgreSQL test is source-backed acceptance, not a fabricated receipt. Merge still requires that this exact test execute successfully against a real PostgreSQL/pgvector service on the final exact head. Until the stacked-PR/migration CI foundation (#1691 and its prerequisites) supplies that hosted database path, a skipped or non-executed PostgreSQL test is not GREEN evidence. Alembic migration compatibility remains a separate required receipt; `Base.metadata.create_all()` in this smoke proves current-model persistence/cascade behavior, not migration-history correctness.
