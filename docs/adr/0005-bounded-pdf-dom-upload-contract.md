# ADR-0005: Bounded PDF DOM upload contract

**Status:** Accepted
**Date:** 2026-08-20
**Decision owner:** Naruon maintainers
**Scope:** Signed `POST /api/data/documents/pdf-dom-recognition` uploads
**Figma File ID:** N/A — backend upload contract; no visual surface.

## Context

Naruon email imports and the NewsDOM sidecar are aligned to a 64 MiB bounded
PDF transport budget. The direct Data workspace upload previously used an
independent 20 MiB limit, so an equivalent manual workflow could reject a
valid email-sized PDF with an avoidable `413`.

## Decision

Set the direct PDF DOM upload and its pending-payload decoder to 64 MiB. Keep
the signed-session boundary, PDF signature validation, one-byte-over-limit
read, base64 persistence contract, and `413` response unchanged. This ADR
records Naruon's consumer-side contract; the NewsDOM sidecar has its own ADR
and must pass its own checks before deployment.

## Consequences

- Email and manual PDF ingestion present the same bounded size expectation.
- Workspace quotas, background-worker limits, and database-capacity monitoring
  remain required because temporary content can be larger.
- No unbounded upload is introduced; malformed or non-PDF payloads continue to
  fail closed before recognition.

## Alternatives rejected

### Keep a separate 20 MiB manual-upload limit

Rejected because it creates a customer-visible workflow inconsistency without a
different safety property after the sidecar contract is raised.

### Remove the upload limit

Rejected because request and database resource use must remain bounded at the
authenticated trust boundary.

## References (APA 7th)

Internet Engineering Task Force. (2022). *HTTP semantics (RFC 9110).* RFC
Editor. https://www.rfc-editor.org/rfc/rfc9110

National Institute of Standards and Technology. (2025). *Secure software
development framework (SSDF) version 1.2* (NIST Special Publication 800-218
Rev. 1, Initial Public Draft). https://doi.org/10.6028/NIST.SP.800-218r1.ipd
