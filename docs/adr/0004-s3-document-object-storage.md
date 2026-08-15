# ADR-0004: S3 raw document object storage

- **Status:** Proposed
- **Date:** 2026-08-15
- **Owners:** Naruon data and platform maintainers
- **Decision scope:** Raw binary workspace-document persistence

## Context

Naruon currently stores a pending PDF as base64 in
`workspace_documents.document_content` until NewsDOM recognition replaces it
with parsed text. That behavior is simple and remains useful for small or
single-node installations, but it couples large immutable binaries to the
transactional PostgreSQL working set and removes the original bytes when parsed
text lands.

Enterprise operators need an object-storage option that:

- scales independently from PostgreSQL;
- preserves the immutable source for reprocessing and provenance;
- works with AWS S3 and controlled S3-compatible services;
- does not expose credentials, bucket topology, tenant identifiers, or public
  object URLs to browser clients;
- keeps PostgreSQL authoritative for authorization, workflow state, parsed
  content, and integrity metadata;
- preserves the current inline database behavior for existing deployments and
  records.

## Decision

Naruon will support two operator-selected document-payload backends:

1. `database` — the existing base64 payload in
   `workspace_documents.document_content`; this remains the default.
2. `s3` — immutable raw PDF bytes in an AWS S3 or S3-compatible HTTPS bucket.

S3-backed documents receive one normalized `document_object_records` row with a
one-to-one foreign key to `workspace_documents`. The row records the storage
backend, bucket, opaque key, content type, byte length, SHA-256 digest, and
lifecycle state. Parsed text continues to land in
`workspace_documents.document_content`; the raw S3 object remains available for
reprocessing and audit.

### Trust and authorization boundary

- API callers never choose endpoint, bucket, object key, encryption, or
  credentials.
- The server creates an opaque object key from a one-way scope digest and the
  generated document ID. It does not include organization IDs, workspace IDs,
  filenames, email addresses, or other PII.
- Reads are server-mediated and continue to use Naruon's signed workspace and
  organization authorization. The first release has no public bucket, ACL,
  browser credential, or presigned URL surface.
- Custom endpoints must use HTTPS, exact-host allowlisting, path addressing,
  globally routable DNS results, and the existing DNS-pinned HTTP transport.
- AWS endpoints are derived from a validated bucket and region and are pinned
  before use.

### Integrity and confidentiality

Every object write:

- signs the request with AWS Signature Version 4;
- signs the exact SHA-256 payload hash;
- sends `x-amz-checksum-sha256`;
- requires `If-None-Match: *` to prevent accidental replacement;
- requires SSE-S3 (`AES256`) or explicitly configured SSE-KMS;
- sends no object ACL.

Every object read validates:

- the metadata row belongs to the requested document;
- the row is active and uses the supported backend;
- the configured bucket matches the stored record;
- the returned byte length equals the stored length;
- the returned SHA-256 equals the stored digest;
- the payload still begins with the PDF signature and respects the upload size
  ceiling.

A database metadata failure after a successful upload triggers a bounded
compensating delete. If compensation itself fails, the original database error
remains authoritative and the log records only a fixed event message; it does
not include credentials, bucket names, object keys, source filenames, provider
response bodies, or exception text.

### Credential scope

The first implementation accepts operator-injected static or temporary
credentials (`access key`, `secret key`, optional `session token`). It does not
call EC2/ECS metadata endpoints or silently discover credentials. Workload
identity and role-based credential providers are a later, separately reviewed
adapter because metadata-service access introduces a distinct SSRF and runtime
trust boundary.

## Alternatives considered

### Keep all bytes in PostgreSQL

Rejected as the only option. It remains supported, but it increases database
backup size and I/O pressure and loses the source bytes when parsed text replaces
the inline field.

### Replace PostgreSQL with S3 as the document source of truth

Rejected. Object storage is not the authority for workspace scope,
authorization, workflow state, parsing status, searchable text, or audit
relationships.

### Store bucket and key on `workspace_documents`

Rejected. A normalized one-to-one object record separates the optional storage
concern from the document entity and allows integrity and lifecycle attributes
to evolve without nullable object-store columns on every document.

### Use a provider SDK immediately

Deferred. Naruon's existing `httpx` and DNS-pinned transport can implement the
small required S3 surface without adding a large dependency and transitive
credential-discovery behavior. The adapter boundary allows a future SDK or
workload-identity implementation after an explicit supply-chain and SSRF review.

### Return presigned URLs to clients

Deferred. Direct client access adds expiry, revocation, CORS, content-disposition,
range-request, and data-leakage contracts that are unnecessary for the initial
NewsDOM worker use case.

## Consequences

### Positive

- Operators can move raw PDF bytes out of the transactional database.
- Existing installations remain compatible by default.
- Original evidence remains available after parsing.
- The same adapter supports AWS S3 and exact-host-controlled S3-compatible
  services.
- Integrity, encryption, and redacted-error requirements are executable tests.

### Negative

- S3-backed uploads span object storage and PostgreSQL without a distributed
  transaction; compensation and orphan monitoring are required.
- Static credential rotation is an operator responsibility in this first slice.
- Custom endpoints require DNS availability when the backend client is built.
- Deleting a database row cascades metadata but does not automatically prove the
  external object was deleted; lifecycle and retention workflows need a later
  explicit deletion worker.

## Verification and release gates

- AWS-published Signature Version 4 example is an executable signing oracle.
- S3 write headers, encryption, checksum, non-overwrite, temporary credentials,
  expected owner, path-style endpoints, safe errors, and read integrity are
  unit-tested with a network-free `httpx.MockTransport`.
- API tests verify database compatibility, S3 metadata persistence, storage
  failure redaction, and compensating deletion.
- NewsDOM worker tests cover both legacy inline and S3-backed reads.
- The migration graph must retain exactly one Alembic head.
- New production modules require 100% statement and branch coverage and complete
  public docstrings.

## References

See [`docs/doctoring/s3-object-storage-references.md`](../doctoring/s3-object-storage-references.md).
