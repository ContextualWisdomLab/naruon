# ADR-0023: Bounded attachment parse-source contract

- **Status:** Proposed; #1469 is unmerged and depends on the owner stack
- **Date:** 2026-08-25
- **Figma file ID:** N/A — backend ingestion and evidence contract; no UX surface
- **Owners:** Naruon ingestion and data-quality maintainers
- **Former proposal ID:** ADR-0006 in #1469, renamed because unrelated open
  proposals already use 0006. This is the same proposal, not an accepted
  superseding decision. No external service decision is accepted here.

## Context and Problem Statement

Naruon accepts authenticated email imports up to 64 MiB, while the deferred
attachment parser previously rejected source payloads above 20 MiB. That split
made a valid upload fail later in parsing and prevented a customer from knowing
whether a file was rejected by transport, parser admission, or an unsupported
format. Unsupported binaries are intentionally not parsed inline and must remain
metadata-only until a separately reviewed parser is available.

A customer importing a 40 MiB published PDF must not lose the admitted source
when recognition is unavailable or rejects its size. Admission, durable storage,
provider capability, and successful extraction are distinct boundaries. The
verified NewsDOM protected-source guard is 20 MiB; its unmerged 64 MiB proposal
does not authorize Naruon to call an unreleased API. Protected integration,
immutable release, exact consumer pin, and runtime compatibility remain gates.

## Decision Drivers

- Preserve admitted source bytes and stable record identity across committed
  worker outcomes and rollback; never relabel metadata as recognized text.
- Bound memory, transport, and storage for untrusted input while retaining
  signed-session, tenant, and workspace ownership.
- Keep the provider contract under NewsDOM ownership and migration/search
  storage repairs under the existing prerequisite stack.

## Considered Options

1. Keep 20 MiB attachment admission: bounded, but rejects files already admitted
   by the email transport. Retain the old limit on protected branches until the
   complete proposal satisfies release and capacity gates.
2. Retain sources up to 64 MiB, separately enforce the verified provider bound,
   and publish only after owner prerequisites are complete: chosen proposal.
3. Send 64 MiB directly to an unreleased provider branch: rejected because it
   bypasses the owner release and can turn accepted work into failed recognition.
4. Remove bounds or discard sources after rejection: rejected because this
   exposes resource exhaustion or irreversible customer data loss.

## Decision Outcome

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

No provider configuration leaves the complete source pending. A real provider
size guard fails the record without changing its source bytes and before DNS or
HTTP transport. Attachments retain `provider_payload_size_exceeded`; workspace
documents currently have only a failure status, not an error-code column.
Both paths classify this expected admission rejection as operational information;
unexpected configuration/recognition failures retain their distinct handling.
Customer guidance should ask for a smaller PDF or an approved service upgrade;
actionable document error detail and retry after an upgrade remain follow-up work.

## Consequences

- The proposal retains attachments larger than 20 MiB through 64 MiB, but does
  not claim that the current provider can recognize them. The PR stays Draft
  until the prerequisites in ADR-0021 and its owner release are satisfied.
- A 64 MiB raw source can expand when base64-encoded in the existing deferred
  content column; the database/object-lifecycle work must move this payload to
  object storage before materially increasing the bound again.
- RFC 4648 encoding makes a 64 MiB source 89,478,488 ASCII bytes before database
  and HTTP overhead. Complete-byte integrity is necessary but does not prove
  acceptable heap usage, index cost, p95 latency, concurrency, or workspace quotas.
- Unsupported binaries remain visible in scoped quality counts without exposing
  their bytes, identifiers, or provider content.
- The contract is independent of any Figma design and has no Storybook scene.

## Confirmation

- `backend/tests/test_attachment_parser.py` round-trips actual 20 MiB + 1 byte
  and 64 MiB unit payloads, rejects 64 MiB + 1 byte, and preserves
  unsupported-binary metadata-only behavior. Synthetic bytes are unit-only.
- `backend/tests/test_newsdom_client.py` sends actual 20 MiB through multipart
  transport and rejects 20 MiB + 1 byte before network validation.
- `backend/tests/test_newsdom_worker.py` uses the real size guard and verifies
  complete pending/failed source retention for attachment and document paths.
- `backend/tests/test_attachment_source_postgres.py` uses the unchanged,
  hash-verified 40,758,835-byte NASA *Earth at Night* PDF on freshly migrated
  PostgreSQL, preserving full bytes and identity through committed pending and
  rejected outcomes and transaction rollback. This is not recognition evidence.
- The import transport remains covered by
  `backend/tests/test_email_import_service.py`.
- The PDF DOM upload contract is being integrated separately by stacked PR
  #1427 / ADR-0021; #1469 inherits it by normal merge. Historical ADR-0005's
  deferral rationale remains in
  [the complete archived proposal](../doctoring/pdf_dom_proposal_history.md).
- Commands, source/release evidence, failure diagnoses, and remaining release
  gates are recorded in [doctoring](../doctoring/bounded-attachment-parse-source-contract.md).

## References (APA 7th)

Fielding, R. T., Nottingham, M., & Reschke, J. (Eds.). (2022). *HTTP
semantics* (RFC 9110). Internet Engineering Task Force.
https://www.rfc-editor.org/rfc/rfc9110.html

Josefsson, S. (2006). *The Base16, Base32, and Base64 data encodings*
(RFC 4648). Internet Engineering Task Force.
https://www.rfc-editor.org/rfc/rfc4648.html

National Aeronautics and Space Administration. (2019). *Earth at night*.
https://www.nasa.gov/ebooks/earth-at-night/

Souppaya, M., Scarfone, K., & Dodson, D. (2022). *Secure software development
framework (SSDF) version 1.1: Recommendations for mitigating the risk of
software vulnerabilities* (NIST Special Publication 800-218). National Institute
of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-218
