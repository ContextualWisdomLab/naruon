# DiskSage file-catalog candidate batch validation

Naruon accepts the bounded
`disksage.file-catalog-candidate-batch` version 1 JSON emitted by DiskSage at:

`POST /api/file-catalog-candidate-batch/validate`

The endpoint is authenticated, accepts at most 2 MiB and 200 candidates, rejects
duplicate JSON keys and unknown fields, and has no database dependency. It does
not call an LLM, contact a cloud provider, persist catalog data, copy a file, or
authorize source eviction.

## Production-time policy

Each selected production date must bind to matching evidence and follow this
exact precedence:

1. embedded metadata;
2. an explicit filename date;
3. filesystem creation time;
4. filesystem modification time.

Filename evidence is auxiliary. Every non-embedded selection must remain
`low` confidence, and a lower-ranked source is rejected whenever the batch
contains applicable higher-ranked evidence.

## Privacy and semantic-layer boundary

The wire type has no source path, destination path, filename, relative path,
provider account identifier, provider object identifier, or locator field.
Unknown fields are rejected. Private title, author, context, worksheet, and
metadata values may be present in the request, but the response does not reflect
them.

Successful validation proves only schema, metadata-precedence, and submitted
claim consistency. It does not prove provenance or safe cloud transfer. Naruon
returns `persisted=false`, `llm_used=false`, `copy_authorized=false`, and
`eviction_authorized=false`.

Ontology projection and steward review remain delegated to
semantic-data-portal. A candidate is not persistable as a file asset until a
content SHA-256 and verified distribution evidence exist.
