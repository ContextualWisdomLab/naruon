# ADR-0005: Quarantine attachments whose bytes disagree with their declared type

**Status:** Accepted (Naruon-local attachment ingestion policy)
**Date:** 2026-08-30
**Decision owner:** Naruon maintainers
**Scope:** Naruon's email-attachment parsing boundary
(`services/attachment_parser.py`, `db.models.Attachment`,
`POST /api/data/attachments/{attachment_uid}/reparse-intent`). This ADR does
not introduce a general-purpose file-type detection library, a virus/malware
scanner, or automatic remediation of quarantined content.

## Context

`parse_email_attachment` classifies an attachment purely from the sender-
supplied `content_type` header (falling back to the filename extension for
generic/missing values). Nothing previously verified that the attachment's
actual bytes matched that claim. A sender — malicious or simply
misconfigured — can label arbitrary binary content (an executable, an image,
an archive) with any `content_type`/extension, and Naruon would either try to
parse it as if it truly were that type, defer it for heavy recognition, or
silently record it as an unsupported binary — three outcomes, none of which
tell an operator or a future worker that the content lied about what it is.

Every other product-facing entity added recently (`TicketTask`,
`CalendarConflictJudgment`, `Document`) exposes an opaque `*_uid` id; `email_attachments`
was the one remaining entity addressable only by its internal sequential
integer id, so it could not be the target of a public, addressable retry
action.

## Decision

1. `services/attachment_parser.py` sniffs the attachment's real bytes against
   a small table of cheap, well-known magic-byte signatures (PDF, PNG, JPEG,
   GIF, ZIP). Text formats have no reliable magic bytes and are not sniffed.
2. When sniffing recognizes a signature that disagrees with the declared or
   extension-resolved type, the attachment is quarantined rather than parsed,
   deferred, or classified as a plain unsupported binary:
   `parse_status = parse_error_code = "content_type_mismatch_quarantined"`.
   The declared type stays in `content_type`; the sniffed (actual) type is
   recorded in `parse_content_type`, so comparing the two columns on a
   quarantined row shows the mismatch directly — no new column is introduced
   for this. The raw bytes are retained (base64, bounded by the same
   `MAX_ATTACHMENT_PARSE_SOURCE_BYTES` used for deferred PDF payloads) so a
   later pass has something to act on, unlike the existing failure statuses
   (`unsupported_content_type`, `parse_size_limit_exceeded`,
   `invalid_pdf_payload`) which discard content.
3. `Attachment` gains an `attachment_uid` opaque id (Alembic `0019`,
   backfilled for any pre-existing rows), following the same
   `<entity>_<uuid4 hex>` convention as `CalendarConflictJudgment.judgment_uid`
   and `TicketTask.task_uid`.
4. `POST /api/data/attachments/{attachment_uid}/reparse-intent` lets a caller
   scoped to the attachment's parent email (via the existing
   `_email_scope_filter` join, since `Attachment` carries no
   `workspace_id`/`user_id` of its own) record that a quarantined attachment
   should be re-evaluated: it transitions `parse_status` from
   `content_type_mismatch_quarantined` to `reparse_pending` and clears
   `parse_error_code`. Calling it on any other status is rejected
   (`422`). Matching the `hwp-conversion-intent`/`pdf-dom-recognition-intent`
   pattern already established for `Document`, this endpoint only records
   intent — it does not itself re-parse. A worker that consumes
   `reparse_pending` was intentionally out of scope for this slice at initial
   authorship, exactly as the NewsDOM PDF worker was a separate follow-up to
   the original deferred-PDF decision — **revised below**: that worker now
   ships in this same PR, after review (see Revisions).

## Alternatives rejected

### Reject mismatched attachments outright at ingestion

Rejected: a genuinely legitimate attachment can carry a wrong `content_type`
header for reasons having nothing to do with intent (a misconfigured mail
client, a lossy import path). Outright rejection would silently drop customer
data the same way an unbounded parse failure would; quarantining preserves the
evidence and gives an explicit, auditable path back to normal handling.

### Add a dedicated `quarantine_status` column

Rejected: every other status-like concept in this codebase
(`Attachment.parse_status`, `Document.document_status`,
`CalendarConflictJudgment.status_code`) is a plain string column with no
separate state table or DB enum. Quarantine is one more value of the existing
`parse_status`/`parse_error_code` columns, not a new state dimension.

### Store the sniffed type in a new column

Rejected: `parse_content_type` already means "the MIME type this attachment
was or would be handled as." Repurposing it for the sniffed type on a
quarantined row keeps that meaning intact (it is still "what this attachment
actually is") while `content_type` keeps its existing meaning ("what the
sender declared"), without adding new schema surface for a single derived
field.

### Synchronously re-parse from the reparse-intent endpoint

Rejected for scope and consistency: no endpoint in this file performs heavy
synchronous work from an `-intent` route today — `hwp-conversion-intent` and
`pdf-dom-recognition-intent` both just flip a status and leave the actual
work to a background worker. Doing real work here would also require
deciding, synchronously, whether the reparse should trust the sender's
original claim or the sniffed type — a decision better made by a dedicated
worker pass than inline in a request handler.

### Use a general-purpose file-type detection library (e.g. `python-magic`)

Rejected for this slice per the Ponytail-adjacent discipline this org applies
before adding a dependency: the org has only ever needed to distinguish a
handful of binary families (currently just PDF, and this ADR's image/zip
additions) from what a sender declares. A half-dozen fixed magic-byte
prefixes checked in Python cover that need with no new dependency, no native
extension, and no supply-chain surface. If a much broader sniffing need
arises later (arbitrary container/archive formats, deep content inspection),
that is the point to re-evaluate a dedicated library against this policy.

## Consequences

- A sender cannot get Naruon to treat disguised binary content as its false
  label by declaring a convenient `content_type` — the actual bytes decide
  when a recognized signature is present.
- Operators/future tooling can address a specific attachment directly via
  `attachment_uid` for the first time; nothing else changes about how
  attachments are listed or displayed in aggregate.
- `reparse_pending` is consumed by `services/attachment_reparse_worker.py`
  (see Revisions below) — a `reparse-intent` call now leads to an actual
  re-evaluation on the next sweep, not an indefinite queue with no consumer.
- **Known, pre-existing, tracked limitation surfaced by this slice, not
  introduced by it:** `_get_scoped_attachment` (and every other attachment/email
  query in `api/data.py`) scopes by `user_id`/`organization_id` only, because
  `Email` itself carries no `workspace_id` column — unlike `Document`,
  `CalendarConflictJudgment`, `CarddavAccount`, and every other workspace-scoped
  entity added since that column existed. A session with the same
  `user_id`/`organization_id` but a different signed `workspace_id` claim can
  therefore read (pre-existing) and, as of this endpoint, mutate (new) another
  workspace's attachments. Closing this properly means adding `workspace_id`
  to `Email` (migration + backfill) and updating every existing email/attachment
  query in `api/data.py` to filter by it — a repo-wide change far outside this
  slice's scope, not something to patch narrowly for one new endpoint. Recorded
  here rather than silently worked around; the fix belongs in its own PR.

## Revisions

Two real gaps were found and fixed after initial review, both narrowing rather
than reversing the original decision:

- **OOXML/ODF/EPUB/JAR false positives.** DOCX, XLSX, PPTX, and other ZIP-based
  container formats sniff as `application/zip` by construction — that is not a
  disguise, it is what those formats are. `_is_genuine_content_type_mismatch`
  now excludes a ZIP sniff whose declared type is itself a known ZIP-container
  family (checked by MIME-type substring, not an exhaustive list, so sibling
  OOXML/ODF variants are covered without enumerating every one). A ZIP sniffed
  under any other declared type (e.g. `application/pdf`) is still quarantined.
- **Oversized mismatches were quarantined with no retained bytes, but
  reparse-intent still accepted them.** A quarantined row whose payload exceeds
  `MAX_ATTACHMENT_PARSE_SOURCE_BYTES` now gets the existing
  `parse_size_limit_exceeded` status instead of
  `content_type_mismatch_quarantined` — the same non-retryable terminal state
  every other oversized attachment in this parser already gets — so
  reparse-intent (which only accepts the quarantine status) can never be
  requested for a row it has nothing left to act on.
- **The reparse-intent follow-up worker, deliberately deferred at first, now
  ships.** `services/attachment_reparse_worker.py` (`AttachmentReparseWorker`,
  wired into `main.py`'s lifespan next to `NewsdomRecognitionWorker`, same
  jittered-loop + PostgreSQL advisory-lock-lease + starvation-free-cursor
  shape) sweeps `reparse_pending` rows and replays
  `parse_email_attachment` against the retained bytes and the attachment's
  original declared `content_type` — deliberately *not* the sniffed type,
  so the worker carries no bespoke "which type do I trust" logic of its own;
  it only re-asks the same classification pipeline the same question, and
  automatically benefits from any future fix to that pipeline (exactly as
  the OOXML fix above already would have, had it existed first). A retained
  payload that fails to decode (not valid base64) moves to a new terminal
  `reparse_payload_invalid` status rather than being swept forever.
- **Two correctness gaps in the worker itself, found on review of the above.**
  (1) The sweep cursor advanced to the batch's last row before any item in it
  was actually processed, so a row whose processing raised an exception (and
  therefore kept its `reparse_pending` status) fell below the cursor and would
  never be reselected until the whole forward queue drained to empty — silent,
  indefinite starvation under continuous reparse-intent traffic. The cursor
  now caps at the row just before the first failure in a batch, keeping that
  row in range for the next sweep. (2) The PostgreSQL advisory lease was
  acquired and released through the same `AsyncSession` used for each item's
  `commit()`/`rollback()`; since `AsyncSession.commit()` returns its
  connection to the pool on every call, the lease's release could run on a
  *different* physical backend connection than the one that acquired it —
  advisory locks are scoped to the acquiring backend session, so a mismatched
  unlock is a silent no-op that leaves the lease stuck until that connection
  is later recycled or closed, silently halting every replica's sweep. The
  lease is now acquired and released on one dedicated connection held open
  for the whole sweep instead. `services/newsdom_worker.py` shares the same
  acquire/release-through-the-per-item-session shape and is believed to carry
  the same latent lease-connection risk; fixing it is out of scope here (its
  own pre-existing, already-shipped code, not touched by this PR) and is
  tracked in `docs/product-technical-gap-baseline.md`.

## References (APA 7th)

Freed, N., & Borenstein, N. (1996). *Multipurpose Internet Mail Extensions
(MIME) Part Two: Media Types* (RFC 2046). RFC Editor.
https://doi.org/10.17487/RFC2046
RFC 2046 is the standard this ADR's "declared type" (the `Content-Type`
header on a MIME body part) refers to; it does not itself specify or require
content-sniffing, which is the gap this ADR addresses.
