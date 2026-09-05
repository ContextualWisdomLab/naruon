# Agent registry semantic field migration

## Problem

The organization-owned `registered_agents.json` contract and its `RegisteredAgent`
internal model used generic single-word names (`name`, `framework`, `entrypoint`,
`description`, `capabilities`, `enabled`, and `raw`). Those names did not carry the
agent-registry bounded-context meaning required by the ContextualWisdomLab naming
contract.

## Selected vocabulary

The canonical registry document now uses:

| Previous field | Canonical field | Bounded-context meaning |
| --- | --- | --- |
| `name` | `agent_display_name` | Human-facing registered-agent display name |
| `framework` | `agent_framework_name` | Runtime framework selected for the registered agent |
| `entrypoint` | `agent_entrypoint` | Import/callable entrypoint used to dispatch that agent |
| `description` | `agent_description` | Registry description of the agent responsibility |
| `capabilities` | `agent_capabilities` | Declared capability identifiers for the registered agent |
| `enabled` | `agent_enabled` | Registry admission state for the agent |
| `writeback` | `writeback_policy` | Writeback governance policy object |
| internal `raw` | `registry_entry_payload` | Preserved source registry entry for diagnostics/inspection |

`agent_id`, `framework_license`, `provider_source`, `writeback_opt_in`,
`writeback_audit_logged`, and `degrades_gracefully` were already semantically
specific multiword names and remain unchanged.

## Compatibility boundary

`backend/services/agent_registry.py` is the anti-corruption boundary. New registry
files publish only the canonical semantic names. The loader still accepts the
previous generic field names as fallbacks so existing deployed registry files can
be upgraded independently. The `RegisteredAgent` object exposed to application
callers uses only the semantic internal names.

If one entry supplies both names with different values, the loader rejects that
entry instead of guessing which registration should control dispatch. Supplying
the same value under both names remains valid during a staged migration.

The compatibility path is covered by
`backend/tests/test_agent_registry.py::test_legacy_registry_keys_remain_accepted_at_adapter_boundary`.
The same test module pins the current registry document and internal dataclass
field names so a future edit cannot silently reintroduce generic owned names.

## Persistence and database impact

This change modifies a versioned repository JSON configuration document, not a
PostgreSQL schema. No table, column, foreign key, index, ORM mapping, UPSERT path,
partition, lock, or read/write topology changes. Existing registry JSON remains
readable through the compatibility adapter; no destructive migration is required.

## Exact-base evidence

The repair branch was created from protected
`develop@042b0c70531b229af3acbd0421a2f23098d848b3`. Fresh exact-head backend,
frontend, security, CodeQL, dependency, coverage, image-validation, Strix, and
review evidence is required before ordinary merge.
