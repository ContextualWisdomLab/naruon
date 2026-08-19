# ADR-0011: Safe metadata parsing for nested email, MP3, and legacy DOC attachments

**Status:** Accepted (Naruon-local attachment parsing policy)
**Date:** 2026-08-19
**Decision owner:** Naruon maintainers
**Scope:** Email attachment ingestion and the content graph. This ADR does not
authorize recursive import, audio decoding, legacy document extraction,
external upload, or provider mutation.

## Context

The private local mailbox-backup audit left 24 unsupported attachments after
the structured Office, ZIP, image, calendar, and vCard coverage: 20 `.eml`, one
`message/rfc822`, one legacy `.doc`, one MP3, and one extensionless generic
binary. The first four have bounded container evidence that can improve search
without pretending to implement a full parser. The last item has no reliable
format evidence and must remain unsupported.

## Decision

1. Naruon registers `nested_email` for `.eml` and `message/rfc822`. It parses
   one bounded message and emits only sanitized subject, sender, and attachment
   count. It does not recursively import or execute the nested message.
2. Naruon registers `audio_metadata` for MP3. It validates a bounded ID3v2
   header or an MPEG frame sync whose layer bits identify Layer III
   (`payload[1] & 0x06 == 0x02`) and emits format, byte count, and ID3
   presence. It does not decode audio or persist tag frames in this slice.
3. Naruon registers `legacy_office_metadata` for legacy `.doc`. It validates
   the Microsoft Compound File/OLE signature and emits container metadata only;
   it does not extract document text or execute macros.
4. These parsers enforce the existing payload limit, return searchable
   `text/plain` metadata when valid, and fail closed without retaining raw bytes
   on malformed or oversized input.
5. Extensionless or otherwise unidentified binary attachments remain
   `unsupported_content_type`. A future parser for them requires reliable
   signature evidence and a new ADR or explicit amendment.

## Alternatives rejected

### Recursively ingest nested email attachments

Rejected because recursion would create duplicate source records, unbounded
work, and a new ownership/threading contract. This slice records only a
bounded manifest.

### Decode MP3 frames or parse legacy Office streams

Rejected because both require a larger format implementation and would turn
metadata coverage into content extraction without a separate retention and
provenance decision.

### Guess the format of extensionless binary data

Rejected because a guessed type can expose arbitrary bytes as trusted content;
the parser remains explicitly unsupported instead.

## Consequences

- Forwarded mail, common MP3 attachments, and legacy DOC containers become
  searchable by bounded metadata.
- The content graph receives no raw binary and no recursive nested-email graph.
- Unsupported, malformed, or oversized payloads remain visible as explicit
  parser states for future operator-authorized replay.

## References (APA 7th)

Internet Engineering Task Force. (2008). *Internet message format (RFC 5322).*
https://www.rfc-editor.org/rfc/rfc5322

RFC 5322 defines the Internet message header/body syntax that bounds this
parser's one-message header inspection and keeps nested mail from becoming a
recursive import operation.

Nilsson, M. (2000). *ID3 tag version 2.4.0—Main structure.* ID3.org.
https://id3.org/id3v2.4.0-structure

The ID3 specification defines the bounded tag header and synchsafe size used
for the metadata-only MP3 check; it does not authorize decoding audio frames
or retaining tag text here.

Microsoft. (2023). *[MS-CFB]: Compound File Binary File Format.* Microsoft
Open Specifications.
https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/53989ce4-7b05-4f8d-829b-d08d6148375b

MS-CFB defines the compound-file signature and container structure used for
the legacy `.doc` recognition boundary; this parser records only that
container evidence and does not traverse streams or execute macros.
