# ADR-0005: Bounded PDF DOM upload contract

**Status:** Proposed
**Date:** 2026-08-20
**Decision owner:** Naruon maintainers
**Scope:** Signed `POST /api/data/documents/pdf-dom-recognition` uploads
**Figma File ID:** N/A — backend upload contract; no visual surface.

## Context

Naruon email imports and the NewsDOM sidecar are being aligned to a 64MiB
bounded PDF transport budget. The direct Data workspace upload still used an
independent 20MiB limit, so a customer could upload a large PDF through email
but receive an avoidable `413` when using the equivalent manual workflow.

## Decision

After NewsDOM publishes an immutable 64MiB transport release and Naruon pins
that exact release, set the direct PDF DOM upload and its pending-payload
decoder to 64MiB. Keep the signed-session boundary, PDF signature validation,
one-byte-over-limit read, base64 persistence contract, and `413` response
unchanged. Until then this consumer change remains Draft and must not be merged.

## Consequences

- After the owner release is pinned, email and manual PDF ingestion present the
  same bounded size expectation to customers.
- The endpoint can persist more temporary database content, so existing
  workspace quotas, background worker limits, and database capacity monitoring
  remain required.
- No unbounded upload is introduced, and malformed or non-PDF payloads continue
  to fail closed before recognition.

## Alternatives rejected

### Keep a separate 20MiB manual-upload limit

Rejected because it creates a customer-visible workflow inconsistency without a
different safety property after the sidecar contract is raised.

### Remove the upload limit

Rejected because request and database resource use must remain bounded at the
authenticated trust boundary.

## References (APA 7th)

Internet Engineering Task Force. (2022). *HTTP semantics (RFC 9110).* RFC
  Editor. https://www.rfc-editor.org/rfc/rfc9110

RFC 9110 supports retaining an explicit `413 Payload Too Large` response when a
request exceeds the server's permitted content size.

National Institute of Standards and Technology. (2025). *Secure software
  development framework (SSDF) version 1.2* (NIST Special Publication 800-218
  Rev. 1, Initial Public Draft). https://doi.org/10.6028/NIST.SP.800-218r1.ipd

The SSDF supports auditable input bounds, regression tests, and operational
controls for untrusted-input boundary changes.

No customer data or source PDF is included; the standards remain linked to their
authoritative publishers.
