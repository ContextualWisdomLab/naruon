# DiskSage reclaim-plan validation

Naruon exposes an authenticated, bounded, stateless validator at
`POST /api/reclaim-plan/validate` for DiskSage `disksage.reclaim-plan` version 1 JSON.

The validator checks the exact operation and reason-code semantics, per-root kind/count
relationships, logical-byte totals, allocation availability, and the hard-link-aware rule that the
total observed allocation may be smaller than the sum of per-root observations. It requires
`physically_reclaimable_bytes` to remain `null` and `status` to remain `unverified`; logical size or
allocated blocks are never accepted as proof of physical recovery.

The endpoint does not inspect, move, delete, or persist any submitted path. Its response is redacted
to schema identity, version, validation scope, and acceptance. A 10 MiB streaming body limit covers
the producer's maximum 1,000 normalized roots with 4,096 UTF-8 bytes per path, including JSON
escaping and per-entry evidence. Duplicate-key rejection, strict types, bounded collections,
UTF-8-byte-aware path limits, and unknown-field rejection keep the validation boundary fail-closed.

DiskSage remains responsible for Rust filesystem observation. Naruon validates only schema and
claim consistency, so this slice does not require a database, Noema, an external LLM,
contextual-orchestrator, semantic-data-portal, pg-erd-cloud, or fast-mlsirm.
