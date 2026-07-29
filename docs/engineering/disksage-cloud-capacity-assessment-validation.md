# DiskSage cloud-capacity assessment validation

Naruon accepts the redacted `disksage.cloud-capacity-assessment` version 1
envelope at authenticated
`POST /api/cloud-capacity-assessment/validate`. The endpoint validates a
DiskSage plan-level capacity claim without contacting iCloud, Microsoft Graph,
or Google Drive, persisting the body, or reflecting submitted evidence.

## Why this is separate from file lineage

Capacity is an observation about a destination account at one time. It is not a
property of a source file and does not prove that a provider accepted a copy.
The envelope therefore remains separate from `disksage.file-lineage` and binds
to the exact redacted plan through
`decision_batch_fingerprint_version: 1` and a lowercase 64-character
`decision_batch_fingerprint`.

This follows the provenance distinction between an entity, the activity that
used it, and contextual evidence about that activity. W3C PROV also distinguishes
consistency validation from a broader trust decision. The endpoint accordingly
returns `validation_scope: schema-and-claim-consistency-only`.

## Validated claims

Version 1 requires capacity snapshot schema version 3 and checks:

- exact integer schema and batch-fingerprint versions, rejecting booleans;
- lowercase 64-character plan and evidence fingerprint shapes;
- the envelope provider and provider-authoritative account scope against the
  nested snapshot;
- iCloud provider-native evidence as personal-account remaining bytes only,
  without invented total, used, trashed, or maximum-upload values;
- OneDrive provider-API evidence with an authoritative personal, organization,
  or shared scope and bounded total, used, and remaining values;
- Google Drive provider-API evidence with usage, trash usage, maximum upload
  size, limited or unlimited quota semantics, and a warning that organization
  pooled storage may be reflected;
- checked unsigned 64-bit `requested + reserve` arithmetic;
- maximum-upload, remaining-capacity, provider-state, and overflow blockers;
- exact sorted and de-duplicated blocker and notice codes; and
- `can_fit` as the deterministic consequence of those claims.

An unavailable snapshot must contain no byte observation, evidence fingerprint,
or account-scope assertion. Its bounded reason code is the sole blocker and
`can_fit` remains `null`.

## Trust and authorization boundary

Naruon does not receive the provider drive ID, Google permission ID, iCloud
account identifier, local cloud-root path, or source-file paths. That redaction
prevents Naruon from independently recomputing the provider-bound evidence
fingerprint or the plan fingerprint. Acceptance verifies their shape and the
submitted claims' internal consistency; it does not authenticate the upstream
provider response.

Naruon also does not revalidate observation freshness, current free capacity,
provider write acceptance, remote-object identity, sync completion, or local
physical reclaimability. A successful validation is never copy approval,
deletion approval, or local-source eviction authorization.

## API safety

The endpoint:

- requires the normal private-API authentication dependency;
- caps the raw body at 64 KiB before Pydantic parsing;
- rejects duplicate JSON object keys, unknown fields, non-strict numeric types,
  and values outside unsigned 64-bit bounds;
- returns only fixed contract metadata; and
- has no database dependency, migration, provider credential, or network call.

Because this is deterministic schema and arithmetic validation, it does not
need Noema, a local or external LLM, fast-mlsirm, semantic-data-portal,
pg-erd-cloud, or a Figma surface.

## Sources

- W3C, [PROV Overview](https://www.w3.org/TR/prov-overview/) and
  [Constraints of the PROV Data Model](https://www.w3.org/TR/prov-constraints/).
  The latter motivates using “valid” to mean internally consistent rather than
  externally trusted.
- Missier, Belhajjame, and Cheney, “The W3C PROV Family of Specifications for
  Modelling Provenance Metadata,” EDBT 2013,
  [doi:10.1145/2452376.2452478](https://doi.org/10.1145/2452376.2452478).
  The paper is cited rather than copied into the repository because
  redistribution permission was not established.
- Microsoft Graph,
  [drive resource](https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0)
  and
  [quota resource](https://learn.microsoft.com/en-us/graph/api/resources/quota?view=graph-rest-1.0).
- Google Drive API,
  [About resource](https://developers.google.com/workspace/drive/api/reference/rest/v3/about).
