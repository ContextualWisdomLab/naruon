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
- **Fixed (see Revisions below): `_get_scoped_attachment` and every other
  attachment/email query in `api/data.py` now scope by `workspace_id` too.**
  `Email` gained a `workspace_id` column (Alembic `0020_email_workspace_scope`),
  and `_email_scope_filter` enforces it unconditionally, matching the pattern
  `_owner_scope_statement` already used for `Document`/`WebdavAccount`/
  `ProjectFolder`. A session with the same `user_id`/`organization_id` but a
  different signed `workspace_id` claim can no longer read or mutate another
  workspace's attachments through this file's queries.
- **Known, still-open, narrower-scoped limitation, tracked as a dedicated
  follow-up:** `Email.owner_filters(user_id, organization_id)` — the
  classmethod backing mail list/search/ontology/threading/Noema-agent email
  reads across `api/emails.py`, `api/search.py`, `api/ontology.py`,
  `services/noema_agent.py`, `services/threading_service.py`, and
  `services/hybrid_retrieval/retrieval_channels.py` — has the identical
  missing-`workspace_id` gap `_email_scope_filter` had, and was deliberately
  left unfixed here: closing it means auditing and updating every one of
  those call sites, a whole-app multi-tenancy change well outside scope for
  a PR whose stated purpose is a calendar-conflict-check tool. Recorded here
  rather than silently worked around; the fix belongs in its own dedicated PR.

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
  for the whole sweep instead.
- **`services/newsdom_worker.py` carried the same two gaps, now fixed to
  match.** It shared `AttachmentReparseWorker`'s acquire/release-through-the-
  per-item-session lease shape and its pre-processing cursor advance, on
  both its attachment and document sweeps. `NewsdomRecognitionWorker` now
  acquires/releases the advisory lock on one dedicated connection opened for
  the whole sweep (`_engine_uses_postgresql()` / `_try_acquire_sweep_lease`
  / `_release_sweep_lease` now take a connection, not a session), and each
  sweep caps its cursor at the point of the first failure instead of the
  batch's last row. The document cursor is a string primary key
  (`Document.document_id`, no `id - 1` to fall back on), so that sweep
  tracks the last row actually confirmed resolved before a failure rather
  than subtracting from the failed row's id — equivalent to the integer
  case for a contiguous key, and correct for a non-contiguous one. Both
  sweeps also re-fetch each row fresh by id before processing (mirroring
  `AttachmentReparseWorker`), since `AsyncSession.rollback()` after an
  earlier item's failure expires every object already loaded in that
  session, and a stale, expired bulk-loaded instance's attribute read would
  raise instead of just isolating that earlier failure.
- **Closed the cross-workspace gap this ADR's own Consequences section
  recorded above, for this file's queries.** `Email` gained a `workspace_id`
  column (Alembic `0020_email_workspace_scope`: add nullable, backfill every
  existing row with `workspace-<organization_id>` — the same convention
  already used by `services/email_import_service.py` and
  `services/project_graph/`, since `Email.organization_id` is `NOT NULL` and
  there is no FK from `Email` to any table that independently carries a real
  `workspace_id` — then set `NOT NULL`). `_email_scope_filter` now applies
  `Email.workspace_id == auth_context.workspace_id` unconditionally, mirroring
  `_owner_scope_statement`'s existing pattern for `Document`/`WebdavAccount`/
  `ProjectFolder`, so every caller of `_get_scoped_attachment` and the
  quality-surface stats helpers picks up the workspace predicate for free
  (they already unpack `*email_scope` into `.where()`). The three production
  call sites that construct new `Email` rows
  (`services/email_import_service.py`, `services/imap_worker.py`,
  `import_fixtures.py`) now populate `workspace_id` the same way. New test:
  `tests/test_data_api.py::test_data_attachment_reparse_intent_is_scoped_to_workspace`
  (same-user/same-org, different-workspace denial — the exact case this ADR
  flagged as unclosed). `Email.owner_filters()` — the separate classmethod
  backing mail list/search/ontology/threading/Noema-agent reads — has the
  identical gap and remains a deliberately separate, tracked follow-up (see
  Consequences above); it was not touched here.
- **CodeRabbit raised the `workspace-<organization_id>` backfill's trust
  boundary; its follow-up correctly rebutted this ADR's first response, and
  the underlying gap is now fixed at the authentication layer.** Its
  concern: if a real signed session's `workspace` claim ever diverges from
  the `workspace-<organization_id>` formula, the migration's backfill (and
  every new row this PR's production call sites write) could misattribute
  rows or make them unreachable. This ADR's first answer claimed that was
  provably impossible for the HMAC session path, reasoning from this repo's
  data-write call sites (no code here ever *writes* a non-conventional
  `workspace_id`). That reasoning missed the actual attack surface:
  `AUTH_SESSION_HMAC_SECRET`-signed sessions are *minted* by an external
  control-plane token issuer (`iss=naruon-control-plane` per
  `docs/operations/auth-key-management.md`) that has no code in this
  repository at all, so nothing here can "prove" what `workspace` value it
  puts in a token. CodeRabbit traced `_auth_context_from_session_payload`
  (`api/auth.py`) directly and showed it requires the `org` and `workspace`
  claims to each be present, but never checks the relationship between
  them — so a session signed with a correct `org` and an arbitrary
  `workspace` value was accepted as-is, for both the HMAC and OIDC paths,
  in production today. Fixed: `_auth_context_from_session_payload` now
  rejects (`401`) any session whose `workspace` claim is not exactly
  `workspace-<organization_id>`, closing the gap at the one place every
  session (HMAC and OIDC alike) is constructed, rather than in the OIDC
  decoder alone or in this migration's backfill formula. This makes
  `auth_context.workspace_id` an actually-enforced invariant instead of an
  assumed convention for every workspace_id-scoped table
  (`Email`, `Document`, `WebdavAccount`, `ProjectFolder`,
  `CalendarConflictJudgment`, `CarddavAccount`), not just this PR's own
  `Email` change. New test:
  `tests/test_auth_real.py::test_build_auth_context_rejects_workspace_claim_not_derived_from_org`.
  Two existing tests asserted specifically on a *different* concern
  (`api/security.py`'s `_require_authoritative_workspace_scope`, which
  unconditionally bars `session_verifier=="hmac"` from `/api/security/access-surface`
  regardless of the workspace claim's value, and a data-quality-surface test
  that only cared the workspace filter clause was present) but happened to
  use a `workspace` value inconsistent with their own `org` claim; both were
  updated to use an org-consistent workspace claim so each isolates the one
  behavior it's actually testing.
- **Devin flagged that `services/email_import_service.py`'s
  `_build_email_object` re-derives `workspace_id` from `organization_id`
  instead of accepting the caller's already-verified
  `auth_context.workspace_id`, reachable at `import_email_files`'s HTTP
  route — confirmed accurate as an architecture observation, and now
  provably inconsequential rather than merely "not currently
  exploitable."** With the authentication-layer fix above,
  `auth_context.workspace_id` is guaranteed equal to the derived value for
  every session that reaches this code, for both the HMAC and OIDC paths —
  not just "for every request path exercised today" as this ADR previously
  (incorrectly) claimed. Threading the real `workspace_id` through
  `import_email_files` → `import_email_uploads` → `_import_single_eml` →
  `_build_email_object` (`imap_worker.py`'s background-poll path has no
  `AuthContext` at all — there is no signed workspace to thread through
  there, so it must keep deriving) remains a reasonable DRY improvement,
  but it is a multi-call-site plumbing change with zero behavioral effect
  now, not a fix for this one's narrower scope.
- **Correction: the "three production call sites" claim above missed a
  fourth `Email`-inserting path, and Devin found it.** `backend/scripts/
  import_fixtures.py::process_zip_file` builds its own bulk-insert
  `batch_values` dict independently of `backend/import_fixtures.py`'s
  `email_obj = Email(...)` construction (already fixed) — a genuinely
  separate script, not the same call site under a confusing shared
  filename. Since `Email.workspace_id` is `NOT NULL`, every nonempty
  archive import through this path failed at commit. Fixed the same way
  (`workspace-<organization_id>` convention, included in both the insert
  values and the `on_conflict_do_update` set). New test:
  `tests/test_import_fixtures.py::test_process_zip_file_batch_insert_includes_workspace_id`
  (the existing `test_process_zip_file` only ever exercised the empty-zip
  path, which never reaches the insert — why this was missed originally).
  Devin also re-flagged `noema_agent.py`'s `tool_search_mail`/
  `tool_read_mail`/`tool_content_graph_query` reading through
  `Email.owner_filters()` without `workspace_id` — traced via `git blame`
  to `b6cb4e6f` (2026-07-13, over a month before this PR): confirmed as
  the identical, already-tracked `Email.owner_filters()` gap two
  paragraphs above, not new exposure from this PR, so left deferred per
  the same narrow-scope decision.

## References (APA 7th)

Freed, N., & Borenstein, N. (1996). *Multipurpose Internet Mail Extensions
(MIME) Part Two: Media Types* (RFC 2046). RFC Editor.
https://doi.org/10.17487/RFC2046
RFC 2046 is the standard this ADR's "declared type" (the `Content-Type`
header on a MIME body part) refers to; it does not itself specify or require
content-sniffing, which is the gap this ADR addresses.
