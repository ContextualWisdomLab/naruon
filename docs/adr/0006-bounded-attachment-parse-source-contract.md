# ADR-0006: Bounded attachment parse-source contract

- **Status:** Accepted for Naruon attachment ingestion
- **Date:** 2026-08-25
- **Figma file ID:** N/A — backend ingestion and evidence contract; no UX surface
- **Owners:** Naruon ingestion and data-quality maintainers

## Context

Naruon accepts authenticated email imports up to 64 MiB, while the deferred
attachment parser previously rejected source payloads above 20 MiB. That split
made a valid upload fail later in parsing and prevented a customer from knowing
whether a file was rejected by transport, parser admission, or an unsupported
format. Unsupported binaries are intentionally not parsed inline and must remain
metadata-only until a separately reviewed parser is available.

## Decision

Use one 64 MiB upper bound for attachment source bytes retained for a deferred
recognition worker. The parser continues to:

1. accept only the existing authenticated import transport;
2. retain validated PDF bytes only for the deferred NewsDOM path;
3. return `parse_size_limit_exceeded` without raw content above 64 MiB;
4. return `unsupported_content_type` with `unsupported_binary` and no raw bytes
   for an unparseable content type; and
5. preserve the parser key, parse status, and error code for the Data quality
   evidence surface.

This is a bounded admission contract, not a promise that every binary format
is parseable. Adding a new parser requires its own dependency, sandbox,
provenance, and regression review.

## Consequences

- Attachments larger than 20 MiB and no larger than 64 MiB can reach deferred
  recognition consistently with the import transport.
- A 64 MiB raw source can expand when base64-encoded in the existing deferred
  content column; the database/object-lifecycle work must move this payload to
  object storage before materially increasing the bound again.
- Unsupported binaries remain visible in scoped quality counts without exposing
  their bytes, identifiers, or provider content.
- The contract is independent of any Figma design and has no Storybook scene.

## Verification

- `backend/tests/test_attachment_parser.py` asserts the 64 MiB boundary is
  above the former 20 MiB parser limit and preserves unsupported-binary
  metadata-only behavior.
- The import transport remains covered by
  `backend/tests/test_email_import_service.py`.
- The existing PDF DOM upload contract is recorded separately in ADR-0005.

## References (APA 7th)

Fielding, R. T., Nottingham, M., & Reschke, J. (Eds.). (2022). *HTTP
semantics* (RFC 9110). Internet Engineering Task Force.
https://www.rfc-editor.org/rfc/rfc9110.html

Souppaya, M., Scarfone, K., & Dodson, D. (2022). *Secure software development
framework (SSDF) version 1.1: Recommendations for mitigating the risk of
software vulnerabilities* (NIST Special Publication 800-218). National Institute
of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-218
