# DiskSage cloud local-allocation evidence

Naruon accepts the exact version 1 JSON emitted by DiskSage's read-only cloud
local-allocation inventory at:

`POST /api/cloud-local-allocation/validate`

This is a root-level observation contract. It is intentionally separate from
`disksage.file-lineage`, which describes one content object and its cloud-copy
lineage. Nesting a root scan in a file envelope would lose traversal bounds,
stop reasons, skipped-entry counts, and output-truncation state.

## Validation boundary

The endpoint authenticates the caller, caps the raw body at 16 MiB, rejects
duplicate JSON keys and unknown fields, and validates the report entirely in
memory. It does not open submitted paths, access a cloud provider, hydrate a
placeholder, write a receipt, persist to the database, or authorize eviction.
Its response is redacted and contains no submitted path or byte count.

Naruon binds the report to the DiskSage v1 implementation invariants:

- traversal limits cannot exceed DiskSage's entry, result, depth, and duration
  caps;
- candidates must be unique lexical descendants of the submitted cloud root;
- every candidate is backed by `filesystem:st-blocks-512` and meets the
  declared minimum allocation threshold;
- file content, embedded metadata, and provider sync must all remain
  unattested in this inventory;
- both `provider-sync-unverified` and
  `human-eviction-approval-required` blockers are mandatory;
- visible candidate allocation must equal the report total unless output is
  explicitly truncated;
- completion, stop reasons, counters, and notices must agree; and
- an external worker hard timeout is accepted only as an empty, incomplete,
  fail-closed report.

This endpoint validates internal consistency only. A successful response is
not evidence that a provider upload finished and is never an eviction permit.

## Standards grounding

The separation follows the [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)
distinction between entities, activities, agents, and provenance bundles. The
inventory is an observation produced by a bounded scan activity; a candidate
path is an observed entity reference; and a later human eviction decision is a
separate accountable activity. Naruon therefore validates the observation as
its own bundle instead of converting it into an approval claim or merging it
with one file's production lineage. No research-model inference is introduced,
so an additional paper PDF or LLM judge is not applicable to this contract.
