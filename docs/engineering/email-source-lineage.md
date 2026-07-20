# Email source lineage

Naruon stores a bounded, versioned evidence envelope in
`email_records.source_lineage_json` for file-imported RFC 822 messages. The
envelope explains which source evidence supports the production time and the
message identity; `email_records.date` alone is not production-time evidence
because the parser uses the import time when the `Date` header is absent or
invalid.

## Evidence contract

```json
{
  "schema_version": 1,
  "source_kind": "rfc822",
  "source_filename": "message.eml",
  "raw_content_sha256": "<64 lowercase hexadecimal characters>",
  "production_time": {
    "selected_value": "2026-06-11T10:00:00+00:00",
    "selected_source": "embedded_date_header",
    "embedded_status": "parsed",
    "evidence_precedence": [
      "embedded_metadata",
      "explicit_filename_date",
      "filesystem_created_at",
      "filesystem_modified_at"
    ]
  },
  "message_identity": {
    "selected_source": "embedded_message_id",
    "embedded_status": "embedded"
  }
}
```

The import path selects the embedded `Date` header only when it parses as an
RFC 822 date. A filename date remains an unselected secondary candidate. The
temporary upload file's creation and modification times are never collected as
source evidence because they describe Naruon's staging file, not the original
message. A valid normalized embedded `Message-ID` is preferred for identity;
otherwise the exact RFC 822 bytes are identified by SHA-256.

Legacy and non-file-imported rows use the database default `{}`. The signed,
owner-scoped email detail and thread APIs return those rows as
`source_lineage: null`. Invalid or unknown evidence envelopes also fail closed
to `null` instead of being reflected to the client.

## Schema and ERD verification

The JSON envelope is intentionally additive to the reconciled single
`email_records` source of truth. It avoids a new relationship until Naruon must
represent multiple acquisitions or a chain of custody for one message. At that
point, promote the contract to an `email_source_lineage_records` child table
with an explicit SQLAlchemy relationship.

Use pg-erd-cloud as a private development verifier, not as a Naruon runtime
dependency:

1. Apply the pre-change and post-change Alembic heads to separate ephemeral
   PostgreSQL databases.
2. Connect pg-erd-cloud with a read-only role restricted to `public` and create
   authenticated, private snapshots.
3. Compare the snapshots and run migration-safety analysis. The expected
   difference is the non-null `email_records.source_lineage_json` JSON column
   with an empty-object server default.
4. Do not use a public share or export for customer schemas, comments, example
   values, or evidence.

Because an ERD cannot describe nested JSON keys, the Pydantic response model,
import tests, migration guard, and PostgreSQL round-trip smoke test are the
authoritative version-1 contract evidence.

No LLM, LLM-as-a-Judge, semantic-data-portal, or contextual-orchestrator call is
required for this deterministic evidence capture. The existing orchestrator
path remains limited to optional batch embeddings and project-graph extraction.
