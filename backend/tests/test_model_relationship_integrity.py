"""Flush-ordering integrity guard for ORM foreign keys (naruon#1041).

SQLAlchemy's unit of work orders INSERTs across different mappers only
through ``relationship()``-derived dependencies — a bare ``ForeignKey``
column does NOT guarantee that the parent row flushes before the child
when both are added in one flush. A missing relationship therefore
turns ``session.add_all([parent, child]); commit()`` into a latent
``ForeignKeyViolationError`` (observed on
agent_run_records -> workflow_definitions).

This guard fails when any foreign-key table pair has no relationship
in either direction, so new models cannot reintroduce the hazard.

Research grounding and the OSMU spin-off evaluation for this
model-agnostic guard are in
docs/engineering/postgres-smoke-evidence-repair.md.
"""

from db.models import Base


def _related_table_pairs() -> set[frozenset]:
    related_pairs: set[frozenset] = set()
    for mapper in Base.registry.mappers:
        for relationship_property in mapper.relationships:
            related_pairs.add(
                frozenset(
                    {
                        mapper.local_table.name,
                        relationship_property.target.name,
                    }
                )
            )
    return related_pairs


def test_every_foreign_key_pair_has_a_relationship():
    related_pairs = _related_table_pairs()
    unrelated_foreign_keys: list[str] = []
    for mapper in Base.registry.mappers:
        for mapped_table in mapper.tables:
            for foreign_key in mapped_table.foreign_keys:
                table_pair = frozenset(
                    {mapped_table.name, foreign_key.column.table.name}
                )
                if len(table_pair) > 1 and table_pair not in related_pairs:
                    unrelated_foreign_keys.append(
                        f"{mapped_table.name}.{foreign_key.parent.name} -> "
                        f"{foreign_key.column.table.name}.{foreign_key.column.name}"
                    )
    assert not unrelated_foreign_keys, (
        "foreign keys without a relationship() break flush ordering for "
        "same-flush parent+child inserts; add the relationship pair: "
        + ", ".join(sorted(unrelated_foreign_keys))
    )
