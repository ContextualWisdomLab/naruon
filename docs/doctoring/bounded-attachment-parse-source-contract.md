# Bounded attachment parse-source contract

## Customer outcome

An email attachment between 20 MiB and 64 MiB is not rejected by a hidden
parser-only limit after transport admission. The Data workspace still reports
unsupported formats explicitly, so the next action is to add a reviewed parser
or use the original provider file rather than treating metadata as extracted
content.

## Contract

`MAX_ATTACHMENT_PARSE_SOURCE_BYTES` is 64 MiB, matching the authenticated email
import budget. The parser is fail-closed:

- supported text formats are parsed inline within the existing character bound;
- PDF bytes are retained only for bounded deferred NewsDOM recognition;
- unsupported binary formats return `unsupported_content_type`,
  `unsupported_binary`, and empty content;
- oversized source bytes return `parse_size_limit_exceeded` and empty content.

This preserves provenance without claiming that an unsupported file was parsed.
The quality surface exposes the parser key and status, not raw attachment bytes,
message IDs, attachment IDs, credentials, or customer payloads.

## Evidence and next action

The parser boundary is tested in
`backend/tests/test_attachment_parser.py`. The import transport is tested in
`backend/tests/test_email_import_service.py`. If a customer needs a currently
unsupported format, add a dedicated parser proposal with sandbox, dependency,
provenance, and exact-head regression evidence before changing the registry.

## Research traceability

The bounded transport and fail-closed error contract are aligned with HTTP
representation semantics (Fielding et al., 2022) and secure development
verification practices (Souppaya et al., 2022). See
[`ADR-0006`](../adr/0006-bounded-attachment-parse-source-contract.md).
