# DiskSage file-lineage handoff

**Status**: Accepted
**Date**: 2026-08-13

## Context

DiskSage can prove a local copy, metadata precedence, review decision, and
provider synchronization evidence. A File Provider placeholder is not itself
proof that a provider API write executed. Naruon already persists content and
knowledge graphs, but the current cloud-copy handoff is only a readiness
summary and cannot represent a general file's provenance or ontology edges.

## Decision

Naruon accepts `disksage.file-lineage` versions 1 and 2 through
`POST /api/disksage/file-lineage`. The request boundary is strict and rejects
unknown fields, unsafe relative paths, unverified copies, and
`provider_write_executed=true` claims. The complete envelope is encrypted at
rest and scoped by authenticated user/workspace. `GET /api/disksage/file-lineage`
returns only `lineage_record_uid`, `lineage_fingerprint`, `schema_version`,
`source_kind`, `archive_kind`, content hashes, `content_bytes`, ontology class,
predicate projection, `provider_name`, provider-native sync state, sync status,
and `created_at`; it does not expose local paths or raw metadata values. A state
such as `pending-upload` is retained as an incomplete provider proof and never
authorizes source eviction.

The payload keeps explicit file → archive destination → provider/account and
review relations. These relation edges follow the same entity/provenance
separation as PROV-O; DiskSage's local ontology remains the domain vocabulary.
The path-free semantic catalog candidate batch is the handoff to
semantic-data-portal. The durable table has an explicit DBML projection at
`docs/architecture/erd/disksage-file-lineage.dbml`; pg-erd-cloud can convert it
to the same snapshot shape as a live database without granting it mutation
authority. The Alembic model remains the runtime source of truth.

## Consequences

- Naruon can index provenance and ontology predicates without authorizing source
  deletion or inventing provider writes.
- The encrypted envelope is not directly queryable for graph search; a later
  scoped projection can be added when a catalog consumer exists.
- DiskSage remains the authority for copy, hash, review, and provider evidence.

## References

- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [W3C OWL 2 overview](https://www.w3.org/TR/owl2-overview/)
