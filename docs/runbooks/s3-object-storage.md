# S3 document object-storage runbook

## Purpose

This runbook enables the optional S3 backend for raw PDFs awaiting NewsDOM
recognition. PostgreSQL remains mandatory and authoritative for document scope,
workflow state, parsed text, checksums, and audit relationships.

The default remains:

```dotenv
OBJECT_STORAGE_BACKEND=database
```

No migration of existing inline documents is required to enable the feature.
Legacy base64 payloads remain readable, while newly uploaded PDFs use the
selected backend.

## AWS S3 configuration

Use a private bucket in the intended data region. Block public access, disable
object ACL use, enable versioning where retention policy permits, and configure
bucket lifecycle rules only after legal-hold and reprocessing requirements are
known.

```dotenv
OBJECT_STORAGE_BACKEND=s3
OBJECT_STORAGE_S3_BUCKET_NAME=naruon-document-evidence
OBJECT_STORAGE_S3_REGION_NAME=ap-northeast-2
OBJECT_STORAGE_S3_ADDRESSING_STYLE=virtual
OBJECT_STORAGE_S3_ACCESS_KEY_ID=<secret-injection>
OBJECT_STORAGE_S3_SECRET_ACCESS_KEY=<secret-injection>
OBJECT_STORAGE_S3_SESSION_TOKEN=
OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION=AES256
OBJECT_STORAGE_S3_KMS_KEY_ID=
OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER=111122223333
OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS=30
```

For SSE-KMS:

```dotenv
OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION=aws:kms
OBJECT_STORAGE_S3_KMS_KEY_ID=arn:aws:kms:ap-northeast-2:111122223333:key/<key-id>
```

Do not put real credentials in `.env.example`, Compose manifests, image layers,
GitHub logs, or source control. Inject them from the deployment secret manager.
The first implementation requires explicit access/secret credentials and may
also use a temporary session token. It does not contact instance metadata or
container credential endpoints.

### Minimum object permissions

Scope the principal to the one bucket/prefix used by Naruon. The initial
runtime requires:

- `s3:PutObject`
- `s3:GetObject`
- `s3:DeleteObject` for metadata-commit compensation

When SSE-KMS is selected, include only the KMS permissions required by the
chosen key policy, normally `kms:Encrypt`, `kms:Decrypt`, and
`kms:GenerateDataKey`, constrained to the S3 service and bucket encryption
context.

## S3-compatible endpoint configuration

Custom endpoints are deliberately stricter than AWS-derived endpoints. They
must be HTTPS, exact-host allowlisted, and path-addressed. Redirects are not
followed.

```dotenv
OBJECT_STORAGE_BACKEND=s3
OBJECT_STORAGE_S3_BUCKET_NAME=naruon-document-evidence
OBJECT_STORAGE_S3_REGION_NAME=us-east-1
OBJECT_STORAGE_S3_ENDPOINT_URL=https://objects.example.com/s3-api
OBJECT_STORAGE_S3_ALLOWED_HOSTS=objects.example.com
OBJECT_STORAGE_S3_ADDRESSING_STYLE=path
OBJECT_STORAGE_S3_ACCESS_KEY_ID=<secret-injection>
OBJECT_STORAGE_S3_SECRET_ACCESS_KEY=<secret-injection>
OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION=AES256
```

The endpoint host must resolve only to globally routable addresses. Naruon pins
the validated address set for outbound connections while preserving the
original hostname for TLS SNI and the HTTP Host header. Internal MinIO or other
private-address deployments require a separately reviewed network policy; they
are not silently enabled by this public-endpoint contract.

## Database migration

Run the normal managed migration path before switching the backend:

```bash
cd backend
alembic upgrade head
```

Confirm that the migration graph has one head and that
`document_object_records` exists with a one-to-one foreign key to
`workspace_documents`.

## Deployment verification

1. Start with `OBJECT_STORAGE_BACKEND=database` and run the existing upload and
   NewsDOM recognition smoke.
2. Apply the migration.
3. Configure the private S3 bucket and credentials in a non-production
   environment.
4. Switch to `OBJECT_STORAGE_BACKEND=s3` and restart the backend.
5. Upload a small PDF through
   `POST /api/data/documents/pdf-dom-recognition`.
6. Confirm:
   - the API returns a generated document ID;
   - `workspace_documents.document_content` is `NULL` while recognition is
     pending;
   - one active `document_object_records` row exists;
   - the object key contains neither the original filename nor tenant/workspace
     identifiers;
   - object metadata shows the configured server-side encryption;
   - NewsDOM recognition replaces `document_content` with parsed text;
   - the object record and raw object remain available for reprocessing.
7. Exercise a deliberately invalid credential in a test environment and verify
   the client receives only `Configured document storage is unavailable.` and
   logs contain no credential, bucket, key, filename, or provider body.

## Observability and incident response

Current failures are surfaced through the upload response or the existing
NewsDOM pending/failed status. Do not add bucket names or object keys to
high-cardinality metric labels.

For a failed metadata commit after successful upload, Naruon attempts a
compensating delete. A fixed log event indicates compensation failure. Treat
that event as a possible orphan and reconcile it using restricted operator
access; never enumerate or expose object locators to end users.

For integrity failures:

1. stop automated reprocessing for the affected deployment;
2. preserve the SQL metadata and object version;
3. compare object version, server access logs, stored byte length, and SHA-256;
4. rotate credentials if unauthorized mutation is plausible;
5. restore from a verified immutable version or backup;
6. record the incident and evidence in the deployment's audit system.

## Rollback

Switching back to the database backend affects only new uploads:

```dotenv
OBJECT_STORAGE_BACKEND=database
```

Do not drop `document_object_records` or delete S3 objects while S3-backed
pending documents exist. The worker selects storage per document: legacy inline
payloads are decoded directly, and S3-backed documents continue to use their
object record even if the default for new uploads changes.

A bulk S3-to-database or database-to-S3 migration is intentionally outside this
slice. It requires an idempotent migration job, per-object verification,
retention decisions, progress checkpoints, and rollback evidence.
