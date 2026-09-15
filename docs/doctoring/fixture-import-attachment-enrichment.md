# Fixture import attachment-enrichment invariant

Date: 2026-09-16
Status: Proposed repair for #1697

## Problem

The root fixture importer built an `Attachment` only after embedding generation succeeded. When enrichment failed, the exception path logged the failure and then committed the enclosing `Email` without the attachment. A derived vector was therefore acting as an accidental persistence prerequisite for source content.

The same function also performed a database `SELECT` before body and attachment embedding. With SQLAlchemy's implicit transaction behavior, that ordering can leave a database transaction open while model/provider I/O is idle.

## Invariant

Parsed source content is authoritative for fixture persistence. Embedding is derived enrichment.

- A parsed attachment must remain attached to the Email aggregate when embedding generation fails; its `embedding` is nullable and may be `None`.
- Body embedding remains required by the current importer contract; if it fails, the email is not imported.
- All body/attachment embedding work completes before the first database statement in this fixture-import path. The database phase contains duplicate detection, thread lookup, aggregate staging, and commit only.
- A database commit failure still rolls the aggregate back and returns failure.

This is intentionally scoped to `backend/import_fixtures.py`; it does not redefine the separate production import service contract.

## Verification

`backend/tests/test_import_fixture_attachment_integrity.py` injects an attachment embedding failure, asserts that embedding work occurs before the first database statement, and verifies that the committed Email aggregate still contains the original filename/content with `embedding=None`.

Hosted PostgreSQL acceptance remains required before merge because mock-session tests prove ordering and aggregate construction, not migration/schema compatibility.
