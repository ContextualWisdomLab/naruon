# Network graph semantic identifiers

## Decision

Naruon's Relationship Context / Network Graph boundary owns the meaning of graph records produced from tenant-scoped email evidence. Organization-owned model names therefore use bounded-context-specific multiword identifiers instead of generic `Node`, `Edge`, `GraphResponse`, `id`, `label`, `source`, `target`, and `weight` names.

The internal contract is now:

| Previous owned name | Specific owned name | Meaning |
| --- | --- | --- |
| `Node` | `NetworkGraphNode` | One email-address node in the relationship graph |
| `id` | `node_id` | Stable node identity within the response |
| `label` | `node_label` | Human-readable node label |
| `Edge` | `NetworkGraphEdge` | One directed sender-recipient relationship |
| `source` | `source_node_id` | Source graph-node identity |
| `target` | `target_node_id` | Target graph-node identity |
| `weight` | `message_count` | Number of observed messages contributing to the relationship |
| `GraphResponse` | `NetworkGraphResponse` | Network graph response aggregate |
| `nodes` | `network_nodes` | Aggregate node collection |
| `edges` | `network_edges` | Aggregate relationship collection |

## Compatibility and anti-corruption boundary

The existing `/api/network/graph` JSON response is already consumed by the Next.js client and local smoke fixtures. Its public wire keys remain `nodes`, `edges`, node `id`/`label`, and edge `source`/`target`/`weight`. Pydantic aliases form the compatibility boundary: organization-owned Python names are specific, while `model_dump(by_alias=True)` and FastAPI response serialization retain the established JSON shape.

The frontend then normalizes backend `source`/`target` into `vis-network`'s `from`/`to` record shape. Generic `id`, `label`, `from`, and `to` at that vendor adapter are externally constrained library vocabulary and are not used as the Naruon domain language.

This change does not alter persisted data, database schema, tenant ownership filters, endpoint paths, response JSON keys, or network authority. No migration or data backfill is required.

The response boundary sorts nodes by email identity and edges by source/target
identity. Identical email evidence therefore produces a deterministic JSON
array order instead of inheriting process-dependent set order or database row
order. This keeps client graph layout inputs, cache validators, screenshots,
and incident comparisons stable without changing graph membership or weights.

## Verification contract

`backend/tests/test_network_graph_naming_contract.py` pins both sides of the boundary: the Python model fields must remain semantically specific and the legacy JSON aliases must remain byte-shape compatible at the object-key level. Repository exact-head CI remains authoritative for the focused test, full backend suite, lint/type checks, security gates, and review evidence.

`backend/tests/test_network_api.py` also pins the complete node and edge order
for deliberately unsorted source rows.

## DDD traceability

- **Bounded context:** Relationship Context / Network Graph.
- **Aggregate response:** `NetworkGraphResponse`.
- **Entities/value records:** `NetworkGraphNode`, `NetworkGraphEdge`.
- **Invariant:** graph-node and relationship meanings are explicit inside Naruon; generic wire/vendor vocabulary is confined to adapters.
- **Invariant:** tenant-scoped email ownership and organization filters remain unchanged.
- **Invariant:** equivalent relationship evidence serializes in canonical node and edge order.
- **Compatibility event:** no public wire-format event is emitted because the external response schema is intentionally preserved.
