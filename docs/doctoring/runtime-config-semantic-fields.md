# Runtime configuration semantic field boundary

## Decision

Naruon's organization-owned runtime-configuration vocabulary uses semantically specific internal names while preserving the established HTTP wire contract at an explicit compatibility boundary.

| Previous internal name | Canonical internal name | External compatibility name |
| --- | --- | --- |
| `version` | `product_version` | `version` |
| `features` | `feature_flags` | `features` |

`product_name` was already a meaningful multiword name and is unchanged.

## Bounded-context rationale

The `/api/runtime-config` payload describes the Naruon product runtime, not an arbitrary versioned object or an arbitrary feature collection. `product_version` therefore names the product-release meaning directly, and `feature_flags` identifies the booleans as runtime capability flags. These names follow the existing Python/TypeScript snake_case API style rather than changing casing for style alone.

The public wire keys `version` and `features` are retained because existing clients may already depend on them. The backend treats them as Pydantic aliases on `RuntimeConfigResponse`; the frontend isolates them in the `RuntimeConfigWire` anti-corruption type and translates them into `RuntimeConfig.product_version` and `RuntimeConfig.feature_flags` before application code receives the value. Generic external names therefore do not remain authoritative organization-owned internal names.

## Compatibility and migration boundary

This repair is serialization-compatible and does not change the HTTP response shape. Backend regression coverage proves semantic construction/deserialization plus legacy alias serialization. Frontend regression coverage proves that the legacy wire payload is translated into the semantic internal shape. Existing runtime-config tests continue to cover fetch caching, in-flight de-duplication, fallback behavior, authentication expectations, and non-secret response content.

No database table, column, index, constraint, sequence, view, function, ORM mapping, migration, foreign key, UPSERT path, partition, or locking behavior is changed. There is no persisted-data migration or rollback transformation; reverting the internal rename would still leave the wire representation unchanged.

## Exact-head evidence

The repair was based on protected `develop@042b0c70531b229af3acbd0421a2f23098d848b3`. The branch was re-fetched before each write and advanced only by ordinary non-force commits. Fresh hosted verification belongs to the final pull-request head and must not be inferred from predecessor commits or local reasoning.
