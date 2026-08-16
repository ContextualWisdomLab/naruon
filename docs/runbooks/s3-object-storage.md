# S3 document object-storage runbook

## Purpose

This runbook enables the optional AWS S3 or S3-compatible backend for raw PDFs
awaiting NewsDOM recognition. PostgreSQL remains mandatory and authoritative for
document scope, workflow state, parsed text, integrity metadata, provider
selection, and audit relationships.

The default remains:

```dotenv
OBJECT_STORAGE_BACKEND=database
```

Legacy base64 payloads remain readable. When the S3 backend is enabled, newly
uploaded PDFs use the active provider in the signed organization scope. Existing
pending inline PDFs can be migrated with the bounded backfill service after the
provider is configured and verified.

## Deployment-level policy

The process environment contains only nonsecret storage policy. Bucket metadata,
encryption choices, and credentials are organization-owned provider records in
PostgreSQL; credential-bearing fields are Fernet-encrypted by Naruon's existing
encrypted-field boundary.

```dotenv
OBJECT_STORAGE_BACKEND=s3
OBJECT_STORAGE_S3_ALLOWED_HOSTS=objects.example.com
OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS=30
OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS=86400
```

`OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS` is the minimum reprocessing window
between successful recognition and remote source deletion. The default is one
day. Operators may set `0` for immediate post-consumption cleanup or a value up
to 2,592,000 seconds (30 days) when their recovery policy requires a longer
window. Legal hold, archival retention, and records-management obligations must
be implemented outside this transient cleanup window rather than silently
retaining application work objects forever.

Do not place S3 access keys, secret keys, session tokens, or KMS key identifiers
in `.env.example`, Compose manifests, image layers, workflow logs, or source
control.

## Organization provider configuration

An authenticated Naruon administrator creates or rotates providers through the
organization-scoped API:

```text
GET    /api/object-storage-providers
POST   /api/object-storage-providers
PATCH  /api/object-storage-providers/{provider_id}
DELETE /api/object-storage-providers/{provider_id}
```

The API never returns stored credential values. Responses expose only redacted
configuration state such as an access-key fingerprint and booleans indicating
whether secret/session/KMS material is configured. Only one provider is active
per organization; object metadata retains the provider that created each object
so rotation or deactivation does not orphan previously stored documents.

### AWS S3 provider example

Create the provider with values equivalent to:

```json
{
  "provider_name": "primary-aws-s3",
  "bucket_name": "naruon-document-evidence",
  "region_name": "ap-northeast-2",
  "endpoint_url": null,
  "addressing_style": "virtual",
  "access_key_id": "<secret-input>",
  "secret_access_key": "<secret-input>",
  "session_token": null,
  "server_side_encryption": "AES256",
  "kms_key_id": null,
  "expected_bucket_owner": "111122223333",
  "is_active": true
}
```

For SSE-KMS, set `server_side_encryption` to `aws:kms` and supply the approved
KMS key identifier in `kms_key_id`.

### Minimum object permissions

Scope the principal to the one bucket/prefix used by the organization. Runtime
requires:

- `s3:PutObject`
- `s3:GetObject`
- `s3:DeleteObject` for compensation, customer deletion, and expired cleanup

When SSE-KMS is selected, include only the KMS permissions required by the
chosen key policy, normally `kms:Encrypt`, `kms:Decrypt`, and
`kms:GenerateDataKey`, constrained to the S3 service and bucket encryption
context.

## S3-compatible endpoint configuration

A custom S3-compatible provider uses the same provider API. The endpoint must be
HTTPS, the exact hostname must appear in `OBJECT_STORAGE_S3_ALLOWED_HOSTS`, and
custom endpoints use path addressing. Redirects are not followed.

Example provider values:

```json
{
  "provider_name": "primary-compatible-store",
  "bucket_name": "naruon-document-evidence",
  "region_name": "us-east-1",
  "endpoint_url": "https://objects.example.com/s3-api",
  "addressing_style": "path",
  "access_key_id": "<secret-input>",
  "secret_access_key": "<secret-input>",
  "server_side_encryption": "AES256",
  "is_active": true
}
```

The endpoint host must resolve only to globally routable addresses. Naruon pins
the validated address set for outbound connections while preserving the
original hostname for TLS SNI and the HTTP Host header. Private-address MinIO,
Ceph RGW, or other internal S3-compatible deployments require a separately
reviewed private-network trust policy; this public-endpoint contract does not
silently weaken SSRF protection to reach them.

## Database migration

Run the normal managed migration path before switching the backend:

```bash
cd backend
alembic upgrade head
```

Confirm that the migration graph has one head and that both normalized tables
exist:

- `document_object_records` — one object lifecycle row per workspace document;
- `object_storage_providers` — organization-scoped encrypted provider registry.

Do not enable the S3 backend for an organization until an active provider exists
and its configuration passes server validation.

## Legacy pending-PDF backfill

The bounded `run_document_object_backfill_batches` service migrates eligible
pending PDF rows from inline base64 storage to the active organization provider.
Each document commits independently. If the relational metadata commit fails
after an object write, Naruon attempts compensation through the same retained
provider authority and leaves the original inline payload retryable.

A backfill run is complete only when a fresh bounded batch selects zero eligible
rows. Do not delete inline customer data merely because an object write
succeeded; the inline payload is cleared only in the same transaction that
persists normalized object metadata.

## Deployment verification

1. Start with `OBJECT_STORAGE_BACKEND=database` and run the existing upload and
   NewsDOM recognition smoke.
2. Apply the managed migrations.
3. Create and validate an organization-scoped provider in a non-production
   environment.
4. Set `OBJECT_STORAGE_BACKEND=s3` and restart the backend.
5. Upload a small PDF through
   `POST /api/data/documents/pdf-dom-recognition`.
6. Confirm:
   - the API returns a generated document ID;
   - `workspace_documents.document_content` is `NULL` while recognition is
     pending;
   - one active `document_object_records` row exists and references the provider;
   - the object key contains neither the original filename nor tenant/workspace
     identifiers;
   - object metadata shows the configured server-side encryption;
   - NewsDOM recognition replaces `document_content` with parsed text and marks
     the object `consumed`;
   - the raw object remains retrievable during the configured reprocessing
     window;
   - the cleanup worker does not select it before the retention cutoff and marks
     it `deleted` only after successful remote deletion.
7. Exercise deliberately invalid credentials in a test environment and verify
   the client receives only the generic storage failure contract and logs contain
   no credential, bucket, key, filename, or provider response body.
8. Rotate/deactivate the active provider and verify pre-existing objects continue
   to resolve through the provider ID retained on their metadata rows.

## Observability and incident response

Upload, read, recognition, backfill, and cleanup failures remain fail-closed and
retryable at their durable PostgreSQL boundary. Do not add bucket names, object
keys, credentials, or customer filenames to high-cardinality metric labels.

For a failed metadata commit after successful upload or backfill, Naruon attempts
a compensating delete. A fixed log event indicates compensation failure. Treat
that event as a possible orphan requiring restricted operator reconciliation;
never enumerate or expose object locators to end users.

For integrity failures:

1. stop automated reprocessing for the affected deployment;
2. preserve SQL metadata and any retained object version;
3. compare provider access logs, stored byte length, and SHA-256 evidence;
4. rotate the organization provider credential if unauthorized mutation is
   plausible;
5. restore from a verified immutable backup or source of record;
6. record the incident and evidence in the deployment audit system.

## Rollback

Switching the deployment default back to the database backend affects only new
uploads:

```dotenv
OBJECT_STORAGE_BACKEND=database
```

Do not drop object/provider tables or bulk-delete S3 objects while S3-backed
pending or retained consumed documents exist. Worker reads resolve storage per
document, so legacy inline payloads remain readable and existing S3-backed
records continue to use their retained provider even after the default changes.

If a backfill must stop, stop the bounded operator run and leave already committed
object-backed rows intact. Unmigrated rows retain their inline payloads. Reversing
already migrated object-backed documents into inline base64 is a separate data
migration and must have explicit capacity, integrity, rollback, and retention
evidence before execution.
