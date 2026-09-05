# Bounded attachment parse-source contract

## Customer outcome

A valid email attachment is no longer discarded by a hidden 20 MiB parser-only
retention ceiling after the authenticated import transport has admitted it. A
PDF that is larger than the currently released NewsDOM provider transport limit
remains visible as `provider_payload_size_exceeded`; it is not reported as
parsed and is not left indefinitely pending. Unsupported formats remain
explicit metadata-only states rather than fabricated extracted content.

## Contract

`MAX_ATTACHMENT_PARSE_SOURCE_BYTES` is a proposed 64 MiB Naruon retention
budget, matching the authenticated email-import ceiling. The parser is
fail-closed:

- supported text formats are parsed inline within the existing character bound;
- validated PDF bytes may be retained only for bounded deferred NewsDOM recognition;
- unsupported binary formats return `unsupported_content_type`,
  `unsupported_binary`, and empty content;
- oversized Naruon source bytes return `parse_size_limit_exceeded` and empty content;
- the NewsDOM client independently enforces the provider transport contract known
  to the released dependency boundary, and the worker persists
  `provider_payload_size_exceeded` when that boundary rejects a retained PDF.

This separation preserves provenance without claiming that a source retained by
Naruon was accepted by an external provider. An open owner PR is evidence of a
candidate contract only; provider-size parity becomes consumable only after an
immutable NewsDOM release is verified and pinned. ADR-0021 owns the separate
direct PDF-DOM upload proposal and the same immutable-release prerequisite.

The quality surface exposes parser key and status, not raw attachment bytes,
message IDs, attachment IDs, credentials, or customer payloads.

## Evidence and next action

- `backend/tests/test_attachment_parser.py` covers the Naruon 64 MiB retention
  boundary and metadata-only unsupported binaries.
- `backend/tests/test_newsdom_client.py` covers provider-size preflight before
  network I/O.
- `backend/tests/test_newsdom_worker.py` covers persistent provider-size failure
  evidence instead of silent pending state.
- [ADR-0021](../adr/0021-bounded-pdf-dom-upload-contract.md) remains Proposed and
  blocked on the immutable owner release/pin; this document does not upgrade it.

If a customer needs a currently unsupported format, add a dedicated parser
proposal with sandbox, dependency, provenance, and exact-head regression
evidence before changing the registry. If provider transport is raised, verify
the immutable owner release first, then bump the Naruon released-contract
boundary and rerun exact-head integration evidence.

## Research traceability

The bounded transport and fail-closed error contract are aligned with HTTP
representation semantics (Fielding et al., 2022) and secure development
verification practices (Souppaya et al., 2022). See
[`ADR-0023`](../adr/0023-bounded-attachment-parse-source-contract.md).
