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

## Verification contract

- A valid sender `Date` may seed the reviewed strong fingerprint.
- Missing and invalid sender dates cannot promote collection time to strong
  evidence.
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
- Existing rows remain conservatively classified when provenance is unknown.

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
