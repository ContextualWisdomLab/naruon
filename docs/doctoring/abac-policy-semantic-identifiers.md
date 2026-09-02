# ABAC policy semantic identifiers

## Decision

Naruon's authorization domain owns semantic ABAC policy vocabulary. `AbacPolicy` therefore uses `resource_action` and `access_conditions` internally, and `evaluate_abac_policy` receives an `abac_policy` parameter. The historical single-word spellings `action` and `conditions` remain only as bounded compatibility aliases/read-only adapters.

This follows the repository-wide naming invariant: casing remains idiomatic Python `snake_case`, while organization-owned names encode their bounded-context meaning. `policy_id` and `resource_type` were already semantically specific and remain unchanged.

## Bounded context and ubiquitous language

The owning context is Authorization / RBAC+ABAC. NIST SP 800-162 defines ABAC decisions in terms of subject/object attributes, requested operations, environment conditions, and policies. In Naruon's existing model, `ResourceAction` already names the operation concept, so `resource_action` is the non-arbitrary specific replacement for bare `action`. `access_conditions` names the attribute constraints evaluated by the policy instead of leaving a generic `conditions` field as internal authority.

## Compatibility boundary

Existing callers may continue to construct `AbacPolicy` with `action=` and `conditions=`. Pydantic aliases translate those legacy names into the semantic internal fields, and read-only compatibility properties preserve historical Python attribute reads. Alias serialization (`model_dump(by_alias=True)`) retains the historical payload keys.

New Naruon-owned code must construct and consume `resource_action` and `access_conditions`. The legacy names are compatibility surface only and must not re-enter `AbacPolicy.model_fields`.

## Persistence and database impact

No table, column, index, constraint, sequence, view, materialized view, ORM mapping, query, UPSERT path, partition key, lock behavior, or read/write topology changes. `AbacPolicy` is not migrated persisted state in this repair, so no backfill or rollback DDL is required. Rollback is the inverse code rename while retaining the same legacy aliases.

## Verification contract

`backend/tests/test_rbac_naming_contract.py` is the focused regression. It requires semantic model fields and the `abac_policy` evaluator parameter while proving legacy construction, legacy attribute reads, and alias serialization remain compatible. `backend/tests/test_rbac.py` exercises the normal evaluation behavior through the semantic vocabulary.

The regression was committed first at `af98b5443fef08fbb44ffe636f4e1e1e2d225f1a`, when production still exposed `action`, `conditions`, and `policy`; the production repair followed in ordinary non-force history.

## Reference

Hu, V. C., Ferraiolo, D., Kuhn, R., Schnitzer, A., Sandlin, K., Miller, R., & Scarfone, K. (2019). *Guide to attribute based access control (ABAC) definition and considerations* (NIST Special Publication 800-162, updated 2019). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-162
