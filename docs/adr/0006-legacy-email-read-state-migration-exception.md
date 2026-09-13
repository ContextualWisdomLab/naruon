# ADR-0006: Preserve apply-time guards in the legacy email read-state migration

**Status:** Proposed
**Date:** 2026-09-14
**Decision owner:** Naruon maintainers
**Scope:** `backend/alembic/versions/0011_email_read_state.py` only

## Context

Naruon's normal migration rule is to use structured Alembic operations rather
than raw DDL. Revision `0011_email_read_state` is a historical compatibility
migration with a narrower problem: one SQL artifact produced by Alembic offline
mode must be safe when it is later applied to either of two database shapes.

A fresh/current database already materializes `email_records.is_read` from the
baseline and may not have the legacy `emails` table. A legacy database can still
have `emails`, and the migration must add `emails.is_read` only when that column
is absent. Downgrade must remove the column only when revision 0011 itself added
it; a pre-existing same-named column is customer data and must survive.

Offline generation has no live target connection. A Python
`sa.inspect(op.get_bind())` decision would therefore either be impossible in
`--sql` mode or would bake one database's answer into an artifact that can later
be applied to a different database. Structured `op.add_column` and
`op.drop_column` operations also do not express "execute this DDL only when a
condition evaluated on the eventual target database is true".

## Decision proposal

Keep the repository-wide structured-Alembic rule. Permit one narrowly scoped
exception for revision 0011: its upgrade and downgrade may execute fixed,
module-level PostgreSQL `DO $$ ... $$` blocks through `op.execute()` so the
legacy relation/column/provenance checks run on the database that actually
receives the offline-generated artifact.

The exception is valid only while all of these invariants hold:

- the SQL is a static module-level literal; no external input, runtime value,
  identifier, or string formatting is allowed;
- relation lookup and DDL resolve through the same search path, using
  `to_regclass('emails')` rather than a schema-agnostic table-name search;
- upgrade adds `is_read` only when the legacy relation exists and the column is
  absent;
- upgrade writes the exact provenance marker
  `0011_email_read_state:added` when it creates the column;
- downgrade drops the column only when that exact marker is present;
- offline SQL generation remains supported and does not need a live bind;
- real PostgreSQL regression coverage proves the legacy-table, absent-table,
  and pre-existing-column cases; scanner suppressions, if needed, remain
  attached only to these fixed calls and state the false-positive boundary;
- this ADR does not authorize raw SQL for new migrations, application queries,
  dynamic identifiers, or any other revision.

The implementation remains proposal-only while PR #1486 is Draft. This ADR
records the decision boundary needed for review; it does not claim protected
branch or release adoption before normal integration.

## Alternatives rejected

### Replace the guard with Python inspection

Rejected because offline migration generation has no authoritative target
connection. Generating different SQL based on whichever database happens to be
available at generation time makes the artifact non-portable and can silently
advance `alembic_version` without applying the legacy change.

### Use unconditional structured `op.add_column` / `op.drop_column`

Rejected because the same artifact must tolerate a database without the legacy
`emails` table, and downgrade must not destroy a same-named column that revision
0011 did not create.

### Remove offline support for the historical branch

Rejected because `scripts/migrate_db.py` exposes Alembic offline SQL generation
as an operational path. A historical migration cannot silently become
online-only while the repository still advertises and tests that path.

### Generalize a reusable raw-SQL migration helper

Rejected. The constraint is specific to one historical compatibility revision.
A reusable helper would turn a bounded exception into a second migration API and
make raw DDL easier to spread.

## Consequences

Reviewers can now evaluate the deviation from the structured-migration rule as
an explicit architecture decision rather than an inline code exception. The
runtime behavior of revision 0011 does not change. The main risk is that a
future edit introduces interpolation or broadens the exception; the static SQL,
provenance regression, real-PostgreSQL cases, and this file-level scope are the
controls against that drift.

If a future Alembic/PostgreSQL mechanism can express the same apply-time
conditional behavior through structured operations while preserving one
portable offline artifact and provenance-safe downgrade, revision 0011 should be
converted and this exception retired rather than expanded.

## Traceability

- Implementation: `backend/alembic/versions/0011_email_read_state.py`
- Real/offline migration coverage: `backend/tests/test_alembic_migrations.py`
- Repository migration rule: `AGENTS.md`, `CLAUDE.md`
- Owning change: PR #1486
