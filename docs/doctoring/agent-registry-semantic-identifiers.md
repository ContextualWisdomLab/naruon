# Agent registry semantic identifiers

## Decision

The workspace agent registry is a Naruon-owned integration boundary. Its canonical JSON catalog and typed Python representation therefore use domain-qualified names rather than generic single-word identifiers. The canonical vocabulary is `agent_name`, `agent_framework`, `agent_entrypoint`, `agent_description`, `agent_capabilities`, `agent_enabled`, and `raw_entry`; the already-specific `agent_id`, `provider_source`, `writeback_opt_in`, `writeback_audit_logged`, and `degrades_gracefully` remain unchanged.

Casing follows the implementation surface: JSON/Python use snake_case here. This decision does not imply that semantically specific camelCase or PascalCase names elsewhere are defects.

## Bounded context and ubiquitous language

**Bounded context:** Workspace Agent Registry.

**Aggregate:** `RegisteredAgent`, keyed by `agent_id`.

**Value objects:** agent display identity (`agent_name`), runtime framework (`agent_framework`), executable entry point (`agent_entrypoint`), capability set (`agent_capabilities`), provider provenance (`provider_source`), and writeback safety posture.

**Invariant:** the registry loader never requires callers to infer what a generic `name`, `framework`, `entrypoint`, `capabilities`, or `enabled` value refers to. The canonical organization-owned catalog uses the `agent_*` vocabulary, and the typed Python object exposes that same vocabulary.

## Compatibility boundary

Historical `registered_agents.json` entries using `name`, `framework`, `entrypoint`, `description`, `capabilities`, or `enabled` are accepted only by the loader's anti-corruption boundary. `_entry_value` maps a legacy key to its semantic equivalent, while `_canonical_raw_entry` removes those generic keys from the internal evidence mapping. New checked-in catalog data uses only the semantic keys.

Read-only Python properties (`name`, `framework`, `entrypoint`, `description`, `capabilities`, `enabled`, `raw`) remain as bounded compatibility aliases for downstream package/submodule consumers. The authoritative dataclass fields are the semantic names, so new code does not depend on the compatibility surface.

## Persistence and operational impact

This repair does not alter a database table, migration, network protocol, provider credential, or writeback authority. The registry remains a local UTF-8 JSON catalog loaded lazily and cached in-process. No UPSERT, locking, hot-partition, or read/write database behavior changes.

Malformed or missing registry files continue to fail closed to an empty registry. Invalid entries without an agent entry point continue to be skipped. `resolve_agent_for_task` now reads `agent_enabled` directly, preserving the existing disabled-agent behavior.

## Verification

The focused registry tests require the canonical semantic attributes and checked-in semantic JSON keys. They also exercise the bounded legacy Python properties so downstream callers can migrate without a flag day. The RED commit preceded the production/config repair: the test required `agent_name`, `agent_framework`, `agent_entrypoint`, `agent_enabled`, `agent_capabilities`, and `raw_entry` while the exact branch still exposed only the legacy generic fields.

Fresh hosted checks on the final unchanged PR head remain the merge authority; predecessor or protected-base results do not transfer.

## Research traceability

Descriptive compound identifiers carry more semantic information and can improve source-code comprehension relative to shorter names, while developers otherwise show substantial variation in naming choices. These findings support qualifying organization-owned identifiers with their domain role rather than enforcing a particular casing convention.

Feitelson, D. G., Mizrahi, A., Noy, N., Ben Shabat, A., Eliyahu, O., & Sheffer, R. (2022). How developers choose names. *IEEE Transactions on Software Engineering, 48*(1), 37–52. https://doi.org/10.1109/TSE.2020.2976920

Schankin, A., Berger, A., Holt, D. V., Hofmeister, J. C., Riedel, T., & Beigl, M. (2018). Descriptive compound identifier names improve source code comprehension. In *Proceedings of the 26th Conference on Program Comprehension* (pp. 31–40). Association for Computing Machinery. https://doi.org/10.1145/3196321.3196332
