# ADR-0023: Bounded attachment parse-source contract

- **Status:** Proposed
- **Date:** 2026-08-25
- **Figma file ID:** N/A — backend ingestion and evidence contract; no UX surface
- **Owners:** Naruon ingestion and data-quality maintainers
- **Former proposal ID:** ADR-0006 in #1469; renumbered after the live open-PR ADR inventory found an unrelated 0006 decision.
- **Depends on:** ADR-0021 for the direct PDF-DOM upload boundary and an immutable released NewsDOM transport contract for provider-side payload acceptance.

## Context

Naruon accepts authenticated email imports up to 64 MiB, while the deferred
attachment parser previously rejected source payloads above 20 MiB. That split
could discard a valid source at parser admission and made it difficult to tell
whether a file was rejected by Naruon transport, parser retention, or the
external recognition provider. Unsupported binaries are intentionally not
parsed inline and remain metadata-only until a separately reviewed parser is
available.

The attachment-source retention budget and the NewsDOM `/parse` transport are
different trust boundaries. This proposal may retain a validated PDF source up
to 64 MiB for deferred work, but the current NewsDOM client continues to enforce
the released provider limit known to this branch. A larger provider transport
must not be assumed from an open owner PR.

## Decision

Prepare one 64 MiB upper bound for attachment source bytes retained by Naruon
for deferred recognition. The parser continues to:

1. accept only the existing authenticated import transport;
2. retain validated PDF bytes only for the deferred NewsDOM path;
3. return `parse_size_limit_exceeded` without raw content above 64 MiB;
4. return `unsupported_content_type` with `unsupported_binary` and no raw bytes
   for an unparseable content type; and
5. preserve parser key, parse status, and error code for Data-quality evidence.

Provider transmission remains fail-closed against the released NewsDOM payload
contract. If a retained PDF exceeds that contract, the worker records
`provider_payload_size_exceeded`; it does not leave the item indefinitely
pending and does not reinterpret an open provider PR as a released capability.

This is a bounded Naruon admission proposal, not a promise that every binary
format or every retained PDF is accepted by an external provider. Adding a new
parser or increasing a provider transport requires its own released dependency,
provenance, sandbox/security review, and regression evidence.

## Consequences

- Naruon no longer has a hidden 20 MiB parser-retention ceiling below the 64 MiB
  authenticated import ceiling.
- PDFs above the currently released NewsDOM transport ceiling remain visible as
  an explicit provider-size failure until an immutable owner release is pinned.
- A 64 MiB raw source expands when base64-encoded in the existing deferred
  content column; object-lifecycle work is required before materially raising
  the retention bound again.
- Unsupported binaries remain visible in scoped quality counts without exposing
  their bytes, identifiers, or provider content.
- The contract is independent of any Figma design and has no Storybook scene.

## Verification

- `backend/tests/test_attachment_parser.py` asserts the 64 MiB Naruon retention
  boundary and preserves unsupported-binary metadata-only behavior.
- `backend/tests/test_newsdom_client.py` asserts provider-size preflight before
  network I/O using the client-owned released-contract bound.
- `backend/tests/test_newsdom_worker.py` asserts an oversized provider payload is
  converted to persistent `provider_payload_size_exceeded` evidence.
- The direct PDF-DOM upload proposal and its immutable-owner-release gate remain
  owned by [ADR-0021](0021-bounded-pdf-dom-upload-contract.md) / #1427.

## References (APA 7th)

Fielding, R. T., Nottingham, M., & Reschke, J. (Eds.). (2022). *HTTP
semantics* (RFC 9110). Internet Engineering Task Force.
https://www.rfc-editor.org/rfc/rfc9110.html

Souppaya, M., Scarfone, K., & Dodson, D. (2022). *Secure software development
framework (SSDF) version 1.1: Recommendations for mitigating the risk of
software vulnerabilities* (NIST Special Publication 800-218). National Institute
of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-218
