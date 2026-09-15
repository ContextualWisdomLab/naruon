# ADR-0002: Compound snake_case names for database objects

- Status: Accepted
- Date: 2026-08-11

## Context

Database names are long-lived API surface. Single-token names and mixed-case
names make migrations, SQL review, and cross-service integration harder to
read consistently.

## Decision

All new or changed PostgreSQL/SQLAlchemy/Alembic database object names must be
lowercase compound `snake_case` with at least two components:

```text
^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$
```

This applies to tables, columns, indexes, constraints, sequences, views,
functions, and other relational objects. Examples: `email_records`,
`status_code`, `ix_email_records_owner_date`. Single-token names such as
`emails`, `id`, `title`, and `status` are not valid for new relational
objects.

GraphDB labels, relationship types, and other graph-native type identifiers are
outside this relational naming rule and must use `CamelCase` or `PascalCase`
(for example, `ProjectTask` or `EmailThread`). They must not be forced through
the relational `snake_case` rule.

Values in relational `project_graph_*` columns such as `object_type` and
`edge_type` are application data, not GraphDB identifiers. They may remain
canonical application enum values until a real GraphDB adapter exists. That
adapter must convert its labels and relationship types to the graph-native
`CamelCase`/`PascalCase` form at the integration boundary.

Existing legacy names remain stable for compatibility. A deliberate rename
requires an explicit migration, dependency inventory, rollback plan, and
verification; this ADR does not authorize opportunistic bulk renames.

## Consequences

- New migrations and ORM metadata must use compound `snake_case` names.
- Review and CI should inspect changed schema definitions and migrations while
  grandfathering untouched legacy objects.
- GraphDB integration can preserve graph-native `CamelCase`/`PascalCase` types
  without weakening the relational boundary.
