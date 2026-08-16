# ADR-0004: S3 raw document object storage

- **Status:** Proposed
- **Date:** 2026-08-15
- **Owners:** Naruon data and platform maintainers
- **Decision scope:** Raw binary workspace-document persistence

## Context

Naruon historically stored a pending PDF as base64 in
`workspace_documents.document_content` until NewsDOM recognition replaced it
with parsed text. That behavior remains useful for small installations, but it
inflates immutable binary payloads inside the transactional PostgreSQL working
set and couples reprocessing evidence to the lifetime of the inline row.

Enterprise operators need an object-storage option that:

- scales raw binary persistence independently from PostgreSQL;
- retains source bytes long enough for bounded reprocessing and recovery;
- works with AWS S3 and controlled S3-compatible services;
- does not expose credentials, bucket topology, tenant identifiers, or public
  object URLs to browser clients;
- keeps PostgreSQL authoritative for authorization, provider selection, workflow
  state, parsed content, integrity metadata, and lifecycle state;
- preserves the current inline database behavior for existing deployments and
  records;
- supports safe migration of pending legacy inline payloads without deleting
  customer data on a partial failure.

## Decision

Naruon supports two deployment-selected document-payload backends:

1. `database` — the existing base64 payload in
   `workspace_documents.document_content`; this remains the default.
2. `s3` — immutable raw PDF bytes in an AWS S3 or S3-compatible HTTPS bucket.

S3-backed documents receive one normalized `document_object_records` row with a
one-to-one foreign key to `workspace_documents`. The row records the retained
provider identity, storage backend, bucket, opaque key, content type, byte
length, SHA-256 digest, and lifecycle timestamps/state. Parsed text continues to
land in `workspace_documents.document_content`.

Organization provider configuration is normalized into
`object_storage_providers`. Bucket, region, endpoint, addressing mode,
encryption mode, expected owner, and credential material are resolved through a
signed organization-scoped database session. Credential-bearing fields use the
existing Fernet-encrypted SQLAlchemy type and are never returned through the
administration API.

The process environment controls only broad deployment policy:

- `OBJECT_STORAGE_BACKEND`;
- exact custom-endpoint host allowlisting;
- request timeout;
- consumed-object reprocessing retention.

### Trust and authorization boundary

- API callers uploading documents never choose endpoint, bucket, object key,
  encryption, or credentials.
- Organization administrators manage provider configuration through the
  authenticated `/api/object-storage-providers` API.
- The server creates an opaque object key from a one-way scope digest and the
  generated document ID. It does not include organization IDs, workspace IDs,
  filenames, email addresses, or other PII.
- Reads are server-mediated and continue to use Naruon's signed workspace and
  organization authorization. There is no public bucket, object ACL, browser
  credential, or presigned URL surface in this decision.
- Custom endpoints must use HTTPS, exact-host allowlisting, path addressing,
  globally routable DNS results, and the existing DNS-pinned HTTP transport.
- AWS endpoints are derived from validated bucket and region values and pinned
  before use.
- Existing objects retain the provider record that created them so later
  credential rotation or active-provider changes do not silently change their
  storage authority.

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
- the row is in a readable lifecycle state and uses the supported backend;
- the retained provider/bucket matches the stored record;
- the returned byte length equals the stored length;
- the returned SHA-256 equals the stored digest;
- the payload still begins with the PDF signature and respects the upload size
  ceiling.

A database metadata failure after a successful upload or backfill triggers a
bounded compensating delete. If compensation itself fails, the original
database error remains authoritative and logs use a fixed redacted event rather
than credentials, bucket names, object keys, source filenames, provider bodies,
or exception text.

### Credential scope and rotation

The current provider registry stores explicit access/secret credentials and an
optional temporary session token in Fernet-encrypted database fields. It does
not call EC2/ECS metadata endpoints or silently discover ambient credentials.
This keeps metadata-service SSRF and runtime identity discovery outside the
initial trust boundary. Workload identity or role-based provider credentials may
be added only behind the same provider abstraction with a separate security ADR
and tests for metadata-service authority, token lifetime, and failure behavior.

Credential rotation updates the provider record without exposing old or new
secrets through read APIs. Old object rows keep the provider identifier, so the
provider record must not be removed while retained objects still depend on it.

### Object lifecycle and reprocessing retention

The lifecycle is explicit:

```text
active -> consumed -> deleted
```

- `active`: raw object backs a pending/retryable document.
- `consumed`: successful recognition has committed parsed text; raw bytes remain
  available during a bounded reprocessing window.
- `deleted`: remote deletion succeeded and the deletion timestamp is committed.

The cleanup worker selects only `consumed` records whose `consumed_at` is older
than `OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS`. The default retention is 86,400
seconds (one day), configurable from 0 through 2,592,000 seconds (30 days).
Cleanup failures roll back only that record and remain retryable without starving
later eligible objects.

This retention is an operational reprocessing window, not a records-management
or legal-hold archive. Durable preservation obligations belong in an explicit
records/backup policy rather than indefinite application-object retention.

### Legacy backfill

A bounded backfill service migrates pending legacy base64 PDFs. Each candidate:

1. revalidates pending PDF state and absence of object metadata;
2. resolves the active organization provider;
3. decodes and validates the legacy payload;
4. writes the object and obtains integrity metadata;
5. inserts `document_object_records` and clears inline content in one database
   transaction;
6. compensates the just-written object if that relational commit fails.

A run reports completion only after a fresh bounded batch selects zero eligible
rows. Already committed object-backed documents are not silently converted back
or deleted during rollback.

## Alternatives considered

### Keep all bytes in PostgreSQL

Rejected as the only option. It remains supported, but increases database backup
size and I/O pressure and couples source-byte retention to the inline document
field.

### Replace PostgreSQL with S3 as the document source of truth

Rejected. Object storage is not the authority for workspace scope,
authorization, workflow state, provider selection, parsing status, searchable
text, or audit relationships.

### Store provider, bucket, and key directly on `workspace_documents`

Rejected. Normalized provider and object lifecycle records separate optional
storage concerns from the document entity, avoid repeated credential/config
fields, and allow lifecycle/provider rotation to evolve without nullable S3
columns on every document.

### Put object-storage credentials in process environment variables

Rejected for the multi-organization runtime. It prevents scoped provider
rotation and makes one process credential set ambient authority for every
organization. The environment is therefore limited to nonsecret deployment
policy while provider credentials are encrypted and organization-scoped.

### Use a provider SDK immediately

Deferred. Naruon's existing `httpx` and DNS-pinned transport implement the small
required S3 REST surface without adding a large dependency and implicit
credential-discovery behavior. The adapter boundary permits a future SDK or
workload-identity implementation after explicit supply-chain and SSRF review.

### Return presigned URLs to clients

Deferred. Direct client access adds expiry, revocation, CORS,
content-disposition, range-request, and data-leakage contracts unnecessary for
the NewsDOM worker path.

### Delete raw objects immediately after recognition

Rejected as the default. Immediate deletion removes the bounded recovery window
needed to re-run recognition after downstream parser/model incidents. Operators
may explicitly configure a zero-second retention when their own source of record
and recovery policy make immediate cleanup appropriate.

## Consequences

### Positive

- Operators can move raw PDF bytes out of the transactional database.
- Existing installations remain compatible by default.
- The same adapter supports AWS S3 and exact-host-controlled S3-compatible
  services.
- Organization-scoped encrypted provider configuration supports controlled
  rotation without ambient process credentials.
- A bounded raw-source window supports reprocessing without indefinite
  retention.
- Backfill and cleanup are retryable database-backed workflows rather than
  one-shot destructive migrations.
- Integrity, encryption, redaction, lifecycle, and retention requirements are
  executable contracts.

### Negative

- S3-backed uploads span object storage and PostgreSQL without a distributed
  transaction; compensation and orphan reconciliation remain operational
  responsibilities.
- The initial credential model still requires explicit secret material rather
  than cloud workload identity.
- Custom endpoints require DNS availability when their backend client is built.
- Real object deletion occurs after a retention delay and therefore consumes
  object-storage capacity during that window.
- A dedicated real PostgreSQL + real object-store integration lane is still
  required in addition to deterministic transport/contract tests.

## Verification and release gates

- AWS-published Signature Version 4 examples remain executable signing oracles.
- S3 write headers, encryption, checksum, non-overwrite, temporary credentials,
  expected owner, path-style endpoints, safe errors, and read integrity are
  tested with deterministic transports.
- Provider API tests verify organization scope, encrypted credential handling,
  redacted responses, activation, rotation, and retained-provider resolution.
- Upload tests verify bounded streaming, PDF signature/size/hash validation,
  metadata persistence, and compensation.
- NewsDOM worker tests cover legacy inline and S3-backed reads plus lifecycle
  transition behavior.
- Backfill tests cover retryability and commit compensation.
- Cleanup tests cover retention cutoff selection, per-object retry, and worker
  boundedness.
- The migration graph must retain exactly one Alembic head.
- New production modules require 100% statement and branch coverage and complete
  public docstrings.
- A release cannot claim #1076 complete until a real PostgreSQL + object-store
  integration lane covers put/get/delete timeout and partial-upload failure
  behavior.

## References

See [`docs/doctoring/s3-object-storage-references.md`](../doctoring/s3-object-storage-references.md).
