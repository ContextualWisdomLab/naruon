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
  POP3 reaches the same `process_fetched_email` boundary and therefore consumes
  the repaired IMAP/POP3 persistence path rather than duplicating the rule.

The canonical migration contract is separately pinned by
`540f6e4ec57ed355263d56e7da78de7ff5310360`: `0018_email_date_provenance`
remains the single provenance revision, with non-null `date_provenance` and an
`unknown` server default. The parallel #1656 `date_evidence` /
`message_id_evidence` migration is not adopted.

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
This avoids a second provenance vocabulary and a sibling migration merely to
record evidence that is already available at ingestion and encoded by the
source-bound identity contract.

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

## POP3 bounded collection window

RFC 1939 assigns message number `1` to the first message in the opened maildrop
and number `n` to the nth message. Naruon's POP3 worker intentionally does not
issue `DELE`; source retention is therefore independent from synchronization.
The predecessor implementation took the first ten `LIST` entries, so a maildrop
larger than the cap could repeatedly revisit its oldest window while newer mail
was never retrieved.

Source-order regression `517ba20f2409012eb28b9c84085103a7c1b04eaa`
requires that predecessor failure mode to be removed. Causal repair
`72c64b46d120ee8c2f3f12ad04114e6a896cb15b` parses all `LIST` message numbers,
sorts them numerically, and retrieves the highest bounded window. Invalid list
entries remain ignored. This changes collection priority only; it does not alter
duplicate identity, retention, or server-side deletion semantics.

That repair is deliberately classified as **partial progress**, not an eventual
backlog guarantee. A static maildrop larger than the cap can still expose the
same highest-numbered window on every poll, leaving older unobserved messages
behind indefinitely. POP3 message numbers are session/maildrop positions, not a
sound durable cross-session cursor. Issue #1717 owns the remaining contract: use
RFC 1939 `UIDL` where supported, persist owner-scoped provider progress, and
prove bounded multi-poll/restart progress without turning provider identity into
Naruon's Message-ID or source-fingerprint truth.

## POP3 session teardown

A successful `RETR` has already returned protocol-visible message bytes before
`QUIT` is attempted. A later transport/protocol error during `QUIT` is cleanup
failure; it must not retroactively discard those bytes and make the sync report a
retrieval failure. Naruon does not issue `DELE`, so preserving the retrieved
bytes does not authorize or imply server-side deletion.

The source-order repair is:

- RED `64baa1e2b71e192d14743bd11da017b4fa33279f` requires a successful `RETR`
  result to survive a `poplib.error_proto` raised by `QUIT`;
- strengthened RED `a74e02b76e236482f2c634a0c54f38450a63b769` also requires an explicit
  transport close when the graceful `QUIT` path fails;
- repair `fa06c566dc29f350ac1e7ff2888ac59bbf5c7ef4` stops a `QUIT` cleanup
  exception from masking already retrieved bytes;
- lifecycle repair `e809575329ff9b9643d7ce93a28556951cdc797a` closes the `poplib`
  transport explicitly after failed `QUIT`, with a bounded warning if close
  itself fails.

This keeps the network lifecycle outside the persistence transaction: RETR and
session cleanup complete before `_import_messages()` opens its database session.

## Verification contract

- A valid sender `Date` may seed the reviewed strong fingerprint only when
  sender/recipients/subject/body evidence is complete.
- Missing and invalid sender dates cannot promote collection time to strong
  evidence.
- A parseable but zone-less Date remains invalid source evidence, while an
  explicit `-0000` Date remains parsed and UTC-comparable.
- Incomplete metadata cannot produce a strong metadata auto-link; import reports
  `dedupe_review_required` while retaining source-bound identity.
- Direct import, IMAP, and the POP3 path through `process_fetched_email` apply
  the same complete-metadata gate.
- Two different raw messages collected at the same instant remain distinct.
- The same raw message collected at different instants has the same fallback
  identity.
- Canonical fallback identity excludes effective collection timestamps and
  provenance flags.
- Canonical fallback serialization accepts only deterministic JSON-native parsed
  values and rejects bytes, unordered collections, custom objects, non-string
  mapping keys, and non-finite numbers instead of coercing them with `str()`.
- IMAP and POP3 pass source bytes through the persistence boundary.
- POP3 source reconstruction restores CRLF after every `RETR` message line.
- A POP3 `QUIT` failure after successful `RETR` cannot discard the retrieved
  bytes, and the transport is explicitly closed when graceful teardown fails.
- Highest-number bounded POP3 selection removes the predecessor oldest-window
  failure mode but is **not** accepted as eventual-backlog progress; #1717 owns
  the durable UIDL-backed completion contract.
- Existing rows remain conservatively classified when provenance is unknown.
- `0018_email_date_provenance` remains the sole canonical provenance migration;
  no parallel `date_evidence` or `message_id_evidence` schema is accepted.

## Claim boundary

Hash equality is evidence that the selected source representation is identical;
it is not proof that two independently authored real-world communications are
the same event. Automatic linkage, clerical review, and distinct-message
outcomes remain separate decisions. No automatic deletion or irreversible
provider action is introduced.

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
