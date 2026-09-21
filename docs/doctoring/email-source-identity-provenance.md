# Email source identity provenance

## Decision

Naruon treats the sender-authored message and the observation process as
different evidence channels. A collection timestamp can be stored as an
operational timestamp, but it cannot become strong duplicate evidence unless a
valid sender `Date` field was genuinely parsed. Messages without that evidence
use a domain-separated SHA-256 identity over immutable RFC 822 source octets. A
deterministic projection of stable parsed fields is used only when the caller
cannot provide transport bytes.

This boundary prevents two distinct messages collected at the same instant from
being linked merely because their observation metadata is similar. It also keeps
a repeated import of the same source stable across collection times.

## Date zone evidence reconciliation

RFC 5322 requires a zone in `date-time`. Python's
`email.utils.parsedate_to_datetime()` can nevertheless return a naive
`datetime` both for a valid `-0000` Date and for a parseable but non-conforming
Date with no zone. Those cases cannot share provenance semantics: `-0000`
retains sender-supplied Date evidence while an omitted zone does not satisfy the
source grammar and must not seed a strong duplicate identity.

The broad #1086 lineage therefore keeps one `date_provenance` vocabulary and
separates those cases before binding a naive value to UTC:

- `-0000` and parser-supported obsolete alphabetic zones with an explicit
  trailing zone remain `parsed` and are normalized to timezone-aware UTC for
  storage/comparison;
- a parseable Date with no trailing zone is `invalid`; `header_date` remains
  absent and the effective stored date is a collection-time UTC fallback;
- the fallback instant is operational data only and never sender metadata.

Source-order RED `66273d51f142fc46f42bfbe64b330f347f80c8fc` adds the zone-less
parser regression. Causal fix `37429ccb805385621844e7625d5da9e5b11eb6ef`
checks for a trailing RFC 5322/obsolete zone before normalizing a naive parsed
value. This inherits the valid #1656 finding into the broad #1195 lineage
without introducing its competing `date_evidence` column or parallel Alembic
revision.

## Complete metadata evidence reconciliation

A parsed Date is necessary but not sufficient for metadata-based automatic
linking. A strong metadata decision also requires non-empty sender, recipients,
subject, and body evidence. Missing any one of those fields makes the metadata
comparison incomplete; the message keeps its raw/canonical source-bound
identity and may enter the review band, but that incomplete tuple cannot create
an automatic metadata link.

The rule is intentionally a gate rather than a new fingerprint format. The
existing strong fingerprint payload remains sender/subject/Date/body so stored
fingerprint compatibility is not silently broken; recipient evidence determines
whether that fingerprint is authoritative enough to use. Message-ID equality
remains an independent identity signal.

The source-order sequence for this repair is:

- `9fdb1207447fe1e47565f92ef57ccd53f02b15f2`: candidate/stored-row RED for
  missing sender/recipients/subject/body evidence;
- `d2ae9d6df3906f1018030ff299e0665a96b5127b`: shared complete-metadata gate in
  the domain classifier;
- `5d68f08b0de6838a818d59636edf2c2f599138ee` →
  `c39f51743598d817edc2f1dfb585a240e0dcc2d7`: direct-import RED then causal
  repair, including deterministic `dedupe_review_required` result semantics;
- `fd4cd4e405b3af30b4458993a4673063350b49d9` →
  `d8a08deb1ad009b2d90de2eafbab5da61ac0cc79`: IMAP RED then causal repair.
  POP3 consumes the same fetched-email persistence boundary rather than
  duplicating dedupe rules.

The canonical migration contract is separately pinned by
`540f6e4ec57ed355263d56e7da78de7ff5310360`: `0018_email_date_provenance`
remains the single message-provenance revision, with non-null
`date_provenance` and an `unknown` server default. The parallel #1656
`date_evidence` / `message_id_evidence` migration is not adopted.

## Message-ID provenance decision

The parser already carries transient `message_id_provenance` (`embedded` or
`missing`) at the ingestion boundary. A missing direct-import Message-ID is
replaced with a deterministic `import-<sha256(raw source)>@local.naruon`
identifier, so equality of two such fallback identifiers is already equality of
the same raw-source digest. Persisting a second `message_id_evidence` column has
no current decision consumer or invariant that cannot be represented by the
existing Message-ID plus source-fingerprint semantics.

Accordingly, #1656's proposed `message_id_evidence` persistence is rejected for
this lineage unless a concrete future consumer proves a storage requirement.
Provider UIDL state is a separate collection-progress concern and must not be
promoted to Naruon's Message-ID or source-fingerprint truth.

## POP3 reconstruction contract

POP3 `RETR` is a multiline response. RFC 1939 requires every transmitted line to
end in CRLF and terminates the response with a separate dot line. Python's
`poplib.POP3.retr()` returns the message as a list of lines without those line
terminators. Naruon therefore reconstructs source bytes by joining returned
message lines with CRLF and adding the final message-line CRLF. The POP3
terminator line is not part of the source message.

The reconstructed bytes are a transport-normalized POP3 representation. They
are not claimed to reproduce server storage outside the protocol-visible
message. IMAP and direct-file ingestion retain their own exact received byte
streams. Duplicate classification remains deterministic because the source kind
is domain separated and because collection time is excluded from fallback
identity.

## POP3 durable bounded progress

RFC 1939 assigns message number `1` to the first message in the opened maildrop
and number `n` to the nth message, but those positions are not durable client
identity. The predecessor implementation first selected the oldest bounded
`LIST` window; repair `72c64b46d120ee8c2f3f12ad04114e6a896cb15b` switched to the
highest current message numbers and removed that particular newest-mail
starvation mode. It still could not guarantee full-maildrop progress because a
static maildrop larger than the cap would repeat the same tail window.

Issue #1717 therefore requires RFC 1939 UIDL-based progress. RFC 1939 defines a
UIDL value as a one-to-70-character server-determined identifier in the range
0x21–0x7E that identifies a message within a maildrop and persists across
sessions. Naruon now keeps this provider progress identity separate from email
identity:

- RED `77d7f23ff603821d3247ac48b88247aaa1c70e8e` defines bounded unseen-UIDL
  selection, current-session renumbering, an explicit UIDL-unavailable fallback,
  and durable observation after successful persistence;
- model `b5344c498ccacaa0b8900be222c6a61bda6e13fe` introduces owner-scoped
  `Pop3ObservedMessage`; migration `970c6d3a124cc26dd50a84b0eee58fb951abeef3`
  adds `0019_pop3_observed_uidl` after the canonical `0018` provenance revision;
- worker repair `5fe993c1363579e439ee4d74ea0190e964315877` asks the server for UIDL,
  filters already observed provider identities, retrieves at most the newest ten
  unseen identities for the current poll, and records the UIDL in the same
  database transaction as successful email persistence using an idempotent
  `(tenant_config_id, provider_uidl)` conflict boundary;
- migration/model contract tests are pinned by
  `c5a997615ab8c4ad3e23463199b2ca98a7a5795d`, and model/index parity is repaired
  by `99e2e7ea6a3f5d79c546afa11f115b253407319a`;
- legacy worker tests were adapted at `3776e5474ec4ae3b5d3d3cadc6513fedfdd0eadf`
  without converting UIDL into message identity.

With UIDL support, a first poll can process the newest bounded unseen set and a
later poll filters those durable observations, exposing the next unseen set even
if current-session message numbers were renumbered. The database session used to
load progress is closed before POP3 network retrieval starts; `_import_messages`
opens a separate short persistence transaction only after RETR/session cleanup.
No explicit DB lock is held across provider I/O.

UIDL is optional in POP3. If the server rejects UIDL or returns a malformed UIDL
listing, Naruon falls back to the bounded highest-number `LIST` window and logs
that durable backlog progress is not proven for that poll. The fallback is a
resource-bounded compatibility policy, not a correctness claim. Naruon still
does not issue `DELE`.

`pop3_observed_messages` intentionally scopes UIDL by `tenant_config_id` and
keeps historical observations because RFC 1939 requires persistence across
sessions. This makes per-account progress reads proportional to stored provider
history; it is a measurable operability/performance surface and must be profiled
before any claim about very large long-lived POP3 mailboxes.

## POP3 partial retrieval and session teardown

A successful `RETR` has already returned protocol-visible message bytes before
later message or session cleanup can fail. A later `RETR`/`QUIT` failure must not
retroactively discard earlier successful bytes.

The teardown source-order repair is:

- RED `64baa1e2b71e192d14743bd11da017b4fa33279f` requires successful RETR bytes
  to survive a `poplib.error_proto` raised by `QUIT`;
- strengthened RED `a74e02b76e236482f2c634a0c54f38450a63b769` also requires an explicit
  transport close when graceful `QUIT` fails;
- repairs `fa06c566dc29f350ac1e7ff2888ac59bbf5c7ef4` and
  `e809575329ff9b9643d7ce93a28556951cdc797a` preserve retrieved bytes and close
  the transport explicitly after failed `QUIT`.

Earlier partial-RETR repair `37a390c59c915016fa2e412c6e77e85e69042510`
correctly preserved messages retrieved before a later failure, but treated every
`poplib.error_proto` from `RETR` as a reason to stop the remaining bounded batch.
RFC 1939 permits repeated commands in TRANSACTION state and defines `-ERR no
such message` as a valid negative `RETR` response. A single permanently rejected
message therefore must not starve later selected UIDLs when the session remains
usable.

The refined source-order repair is:

- RED `d9c87082355fd133a5f4ed9715c560eaee28b211` requires a standards-conforming
  per-message `-ERR` to leave that message unobserved while continuing to later
  messages in both UIDL and bounded `LIST` fallback paths; an `OSError` remains a
  transport-stop condition;
- initial repair `38803cc59be9cee2f72be5f48a9c3c9f1aca402e` separates POP3 protocol
  exceptions from transport exceptions;
- hardening RED `7606387c829e27845633d180642369547d23336b` proves that an unexpected
  non-`-ERR` protocol exception must not be treated as a safe per-message
  rejection;
- final repair `a5d7d21011cf96548cce18b8119a553123a25ab5` continues only when the
  protocol exception carries an RFC-style `-ERR` response and stops the
  remaining batch on transport loss or malformed/unexpected protocol response.

Only successfully returned messages can be persisted and only their UIDLs can
become observed. A rejected UIDL therefore remains eligible for retry, while one
persistent message-level rejection no longer blocks later selected messages in
that poll. Naruon still does not issue `DELE`; preserving or continuing retrieval
does not authorize or imply server-side deletion.

## Verification contract

- A valid sender `Date` may seed the reviewed strong fingerprint only when
  sender/recipients/subject/body evidence is complete.
- Missing and invalid sender dates cannot promote collection time to strong
  evidence.
- A parseable but zone-less Date remains invalid source evidence, while an
  explicit `-0000` Date remains parsed and UTC-comparable.
- Incomplete metadata cannot produce a strong metadata auto-link; import reports
  `dedupe_review_required` while retaining source-bound identity.
- Direct import, IMAP, and POP3 apply the same source-bound persistence rule.
- Two different raw messages collected at the same instant remain distinct; the
  same raw message collected at different instants has the same fallback
  identity.
- Canonical fallback identity excludes collection timestamps/provenance flags and
  rejects unsupported serialization types instead of coercing them with
  `str()`.
- IMAP and POP3 pass source bytes through the persistence boundary; POP3 source
  reconstruction restores CRLF after every `RETR` message line.
- With UIDL support, a bounded poll retrieves only unseen provider identities;
  persisted observations survive reconnects and current-session renumbering.
- UIDL is transport progress identity only. It cannot replace Message-ID,
  source-fingerprint, or dedupe evidence.
- UIDL-unavailable/malformed fallback is explicitly compatibility-only and does
  not claim eventual backlog completion.
- A per-message RFC-style RETR `-ERR` leaves that identity retryable and does not
  starve later selected messages; transport loss or malformed protocol stops the
  remaining batch.
- A QUIT failure preserves retrieved bytes and explicitly closes the transport.
- `0018_email_date_provenance` remains the sole message-provenance migration;
  `0019_pop3_observed_uidl` succeeds it for provider collection state rather than
  introducing parallel message provenance.

The source-order tests and implementation above are not themselves hosted GREEN
evidence. PostgreSQL migration execution, repository tests/security/coverage,
current-head independent review, restart acceptance, and large-mailbox
performance still require exact-head receipts before #1717 or #1195 can be
accepted complete.

## Claim boundary

Hash equality is evidence that the selected source representation is identical;
it is not proof that two independently authored real-world communications are
the same event. Automatic linkage, clerical review, and distinct-message
outcomes remain separate decisions. Provider UIDL proves only the server's
maildrop identity contract. No automatic deletion or irreversible provider
action is introduced.

## References

Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. *Journal
of the American Statistical Association, 64*(328), 1183–1210.
https://doi.org/10.1080/01621459.1969.10501049

Fellegi and Sunter formalize record linkage by comparing field-level evidence
under match and non-match hypotheses. The resulting evidence score is evaluated
against two decision thresholds: sufficiently strong evidence produces a link,
sufficiently weak evidence produces a non-link, and the intermediate region is
reserved for clerical review. Naruon maps those three outcomes to `auto_link`,
`distinct`, and `review_required` while keeping provenance-gated evidence out of
the automatic-link region.

Myers, J., & Rose, M. (1996). *Post Office Protocol—Version 3* (RFC 1939;
STD 53). Internet Engineering Task Force. https://doi.org/10.17487/RFC1939

Resnick, P. (2008). *Internet message format* (RFC 5322). Internet Engineering
Task Force. https://doi.org/10.17487/RFC5322
