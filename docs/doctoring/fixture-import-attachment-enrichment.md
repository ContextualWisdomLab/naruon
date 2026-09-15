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

`backend/tests/test_import_fixture_attachment_integrity.py` covers two causal paths. It forces attachment embedding generation to fail and verifies that all enrichment occurs after the initial read transaction is released, then confirms the committed Email aggregate still contains the original filename/content with `embedding=None`. A duplicate-path regression verifies that enrichment and thread lookup are never invoked and that the read transaction is rolled back before returning.

Existing fixture-import test doubles now implement the rollback operation required by the real session protocol so they continue to exercise the same transaction boundary rather than bypassing it.

Real PostgreSQL acceptance remains mandatory before merge because mocked sessions prove ordering and aggregate construction, not PostgreSQL vector-null persistence, relationship cascade behavior, or migration/schema compatibility. The exact acceptance receipt belongs in the PR authority once the hosted database job reaches a terminal result.
