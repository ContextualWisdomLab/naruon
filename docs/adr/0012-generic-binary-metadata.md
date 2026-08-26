# ADR-0012: Safe metadata for generic binary attachments

**Status:** Accepted (Naruon-local attachment parsing policy)
**Date:** 2026-08-20
**Decision owner:** Naruon maintainers
**Scope:** Email attachment ingestion and the content graph. This ADR does not
authorize format detection, binary decoding, raw-byte retention, or external
upload.
**Figma File ID:** N/A — backend generic-binary parsing; no visual surface.

## Context

Some real attachments arrive with a generic or otherwise unrecognized MIME
type and no trustworthy extension or signature. Treating those files as text
risks indexing arbitrary binary data, while rejecting them entirely makes the
attachment invisible to search and makes the parser surface look like a size
limit. The existing image, Office, archive, media, and PDF parsers retain their
own bounded format-specific contracts.

## Decision

Naruon registers `binary_metadata` for generic and otherwise unrecognized
binary MIME types and returns only a `text/plain` summary containing the
normalized MIME type and exact byte count. The parser accepts payloads larger
than 20 MiB within the signed email import's 64 MiB transport ceiling and does
not use the image animation scan window or any other 1 MiB ceiling. It does
not guess a format from weak evidence, decode bytes, hash bytes, upload bytes,
or retain the payload in the parse result.

A declared MIME value alone is not format evidence. Unrecognized MIME values
without a recognized format signature are metadata-parseable, not
format-parseable. A future format-specific parser requires reliable signature
evidence, focused tests, and a new ADR or explicit amendment.

## Alternatives rejected

### Keep all unrecognized binaries unsupported

Rejected because it hides safe, useful provenance metadata and makes an
operator-visible unsupported state indistinguishable from a parser-size
failure. The metadata path makes no format claim, including for non-generic
MIME values.

### Guess a format or decode arbitrary bytes

Rejected because MIME and extensionless input do not establish a trustworthy
format boundary; guessed decoding could expose arbitrary bytes as content.

## Consequences

- Generic binary attachments remain visible and searchable by safe metadata.
- A large generic attachment is not rejected by the former 1 MiB scan window.
- The content graph receives no raw binary and makes no format claim.
- Existing persisted `unsupported_binary` records remain valid historical
  states; new unrecognized binary imports use `binary_metadata`.

## References (APA 7th)

Internet Engineering Task Force. (2013). *Media type specifications and
  registration procedures (RFC 6838).* https://www.rfc-editor.org/rfc/rfc6838

RFC 6838 supports treating the declared media type as a registered metadata
value while keeping format-specific processing as a separate contract.

Späth, C., Mainka, C., Mladenov, V., & Schwenk, J. (2016). *SoK: XML parser
vulnerabilities.* In *10th USENIX Workshop on Offensive Technologies (WOOT
16).* USENIX Association.
https://www.usenix.org/conference/woot16/workshop-program/presentation/spath

The study's systematic analysis of unsafe XML parser features and denial of
service vectors supports this ADR's fail-closed boundary: generic binaries
receive only normalized MIME and byte-count metadata, while any future
format-specific parser must establish reliable evidence and use bounded,
hardened parsing. The paper PDF is linked by USENIX but is not redistributed
here because USENIX states that copyright remains with the individual authors.
