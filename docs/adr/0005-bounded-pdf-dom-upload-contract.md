# ADR-0005: Bounded PDF DOM upload contract

**Status:** Proposed
**Date:** 2026-08-20
**Decision owner:** Naruon maintainers
**Scope:** Signed `POST /api/data/documents/pdf-dom-recognition` uploads
**Figma File ID:** N/A — backend upload contract; no visual surface.

## Context

Naruon email imports and deferred attachment admission use a 64 MiB bounded
transport budget. The direct Data workspace PDF-DOM endpoint and its NewsDOM
sidecar contract remain independently bounded at 20 MiB on the current
protected branch; this record preserves the proposed alignment without
claiming that the separate transport change has shipped.

## Decision

Retain the current 20 MiB direct PDF-DOM upload and decoder boundary until the
separate transport change is reviewed and integrated. Keep the signed-session
boundary, PDF signature validation, one-byte-over-limit read, base64
persistence contract, and `413` response unchanged. A future alignment to the
64 MiB import budget requires sidecar confirmation, capacity evidence, and a
new current-head review; this ADR does not authorize that change.

## Consequences

- Email and manual PDF ingestion currently have explicit, separately governed
  bounded contracts (64 MiB import/deferred admission; 20 MiB direct DOM).
- Workspace quotas, background-worker limits, and database-capacity monitoring
  remain required because temporary content can be larger.
- No unbounded upload is introduced; malformed or non-PDF payloads continue to
  fail closed before recognition.

## Alternatives rejected

### Align the manual endpoint immediately

Deferred until the sidecar and storage capacity contract are independently
verified; changing only the Naruon endpoint would create a customer-visible
failure later in recognition.

### Remove the upload limit

Rejected because request and database resource use must remain bounded at the
authenticated trust boundary.

## References (APA 7th)

Internet Engineering Task Force. (2022). *HTTP semantics (RFC 9110).* RFC
Editor. https://www.rfc-editor.org/rfc/rfc9110

National Institute of Standards and Technology. (2025). *Secure software
development framework (SSDF) version 1.2* (NIST Special Publication 800-218
Rev. 1, Initial Public Draft). https://doi.org/10.6028/NIST.SP.800-218r1.ipd
