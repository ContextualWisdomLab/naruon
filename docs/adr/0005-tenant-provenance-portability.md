# ADR-0005: Package tenant provenance as a deterministic integrity envelope

**Status:** Accepted for the workspace project-evidence closure
**Date:** 2026-08-31
**Decision owner:** Naruon maintainers
**Scope:** Export and reimport of the email-derived provenance records cited by
one signed-session workspace. This decision does not claim full mailbox,
credential, connector, binary-object, or arbitrary multi-workspace portability.

## Context

GA-1 requires a buyer to leave, restore, or migrate without losing provenance.
Naruon persists email sources, attachment parse evidence, DOM nodes and
segments, structural edges, project objects and edges, and correction history,
but has no portable round-trip contract. Integer database keys cannot serve as
portable identity and credentials must never enter an export.

`email_records` has owner and organization scope but no `workspace_id`. Exporting
all owner mail as a workspace bundle could therefore cross a same-organization
workspace boundary. The first safe closure begins with project graph rows scoped
to the exact workspace and includes only their cited source records.

## Decision

1. Package the exact project-evidence closure as a deterministic ZIP containing
   a BagIt 1.0 envelope, `data/records.json`, and RO-Crate 1.3 JSON-LD metadata.
2. Use stable logical UIDs in the payload. Never serialize or restore sequential
   database primary keys. Import resolves new keys in foreign-key order.
3. Canonical JSON uses UTF-8, no BOM, no insignificant whitespace, sorted object
   keys, and pre-sorted set-like arrays. SHA-512 manifests cover exact bytes.
4. Reject unsafe or colliding ZIP paths, unlisted files, checksum mismatch,
   unsupported profiles, dangling references, scope mismatch, duplicate logical
   UIDs, and non-finite numbers before mutation.
5. Reimport is idempotent for target scope, bundle UID, and manifest digest.
   Existing identical records are skipped; conflicting records fail closed.
   Absence never means deletion and v1 has no tombstones.
6. Export plaintext evidence required for restoration, including email and
   parser-confirmed textual attachment content. Exclude credentials, encrypted
   secret rows, embeddings, raw binary documents, provider URLs or tokens, and
   legacy unscoped audit details. Embeddings are regenerated after import.
7. Signed-session API routes use the current `user_id`, `organization_id`, and
   `workspace_id`; bundle payload scope cannot override target authority. HMAC
   fallback sessions are rejected because they do not prove workspace
   membership; OIDC or server verification is required outside tests.
8. Full mailbox/customer-exit completion remains open until email ownership has
   an explicit workspace dimension and binary object lifecycle is portable.

## Alternatives rejected

- **Database dump:** leaks implementation keys and secrets and couples versions.
- **RO-Crate alone:** describes data but is not a byte-integrity envelope.
- **BagIt alone:** verifies opaque bytes but does not describe provenance.
- **Data Transfer Project adapter first:** does not define an offline archive.
- **Export all owner emails:** unsafe while `email_records` lacks workspace scope.

## Consequences

- Buyers gain a verifiable first portability slice over evidence used for
  project judgments and corrections.
- The importer validates the complete closure before one database transaction.
- Integrity hashes detect corruption but do not authenticate replacement; bundle
  signing is a later profile revision.
- The product baseline keeps full tenant/mailbox, binary-object, credential,
  provider/connector-state, and audit-history export/reimport open.

## References (APA 7th)

Kunze, J., Littman, J., Madden, L., Scancella, J., & Adams, C. (2018). *The
BagIt file packaging format (V1.0)* (RFC 8493). RFC Editor.
https://doi.org/10.17487/RFC8493

Lebo, T., Sahoo, S., & McGuinness, D. (Eds.). (2013). *PROV-O: The PROV
ontology*. World Wide Web Consortium. https://www.w3.org/TR/prov-o/

Rundgren, A., Jordan, B., & Erdtman, S. (2020). *JSON canonicalization scheme
(JCS)* (RFC 8785). RFC Editor. https://doi.org/10.17487/RFC8785

RO-Crate Community. (2026). *RO-Crate metadata specification 1.3*.
https://doi.org/10.5281/zenodo.20720080

The standards are cited and linked instead of copied; redistribution terms for
the complete referenced publications were not all established for this PR.
