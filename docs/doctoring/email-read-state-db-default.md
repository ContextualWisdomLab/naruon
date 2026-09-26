# Email read-state database default recovery

## Incident and scope

On `develop@042b0c70531b229af3acbd0421a2f23098d848b3`, a fresh PostgreSQL 16/pgvector database failed `alembic upgrade head` at revision `0001`: the bootstrap tried to index the retired `emails` table. Two PostgreSQL smoke tests also failed on `email_records.is_read` `NOT NULL` because their SQL inserts omitted that column. Both failures reproduced in an isolated database before this repair. The earlier [#1381](https://github.com/ContextualWisdomLab/naruon/pull/1381) contained the database default and migration, but it merged into a stacked feature branch; neither current `develop` nor [#1417](https://github.com/ContextualWisdomLab/naruon/pull/1417)'s current tree contains them.

## Repair and verification

The model now defines a database-side `true` default, while the existing Python-side default remains. The retired index is removed from bootstrap, revision `0011` checks for the legacy table and column, and an additive revision sets `email_records.is_read` to `NOT NULL DEFAULT true` on existing databases. Downgrades preserve read-state data. SQLAlchemy distinguishes Python-side defaults from DDL server defaults, which is why a raw SQL insert bypassed the former (SQLAlchemy, n.d.). Alembic supports changing both nullability and server defaults in a column alteration (Alembic, n.d.).

On an isolated PostgreSQL 16/pgvector database, fresh upgrade to the new head passed. Restamping an existing schema to `0017`, removing its default, and upgrading restored `true|NO` in `information_schema.columns`. A second repair drill started with a nullable column and a NULL row; upgrade produced `true|NO|true` for the default, nullability, and repaired row. The two previously red smoke tests passed, and the backend suite passed with `1836 passed, 3 skipped` while excluding `tests/real_datasets` from collection. The proposed `0018_email_record_read_state` and the open S3 branch's `0018_document_object_records` are parallel children of `0017`; a later integration must merge those migration heads before the S3 branch lands.

## References

Alembic. (n.d.). *Operation reference*. https://alembic.sqlalchemy.org/en/latest/ops.html

SQLAlchemy. (n.d.). *Column INSERT/UPDATE defaults*. https://docs.sqlalchemy.org/en/20/core/defaults.html
