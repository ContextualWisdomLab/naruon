# Safe nested, media, and legacy attachment metadata doctoring record

## Evidence

The private local audit of the 2026-07-31 Inbox backup initially left 24
unsupported attachments: 20 nested `.eml`, one `message/rfc822`, one legacy
`.doc`, one MP3, and one extensionless generic binary. After the bounded
metadata parsers, the extensionless generic binary is represented by safe MIME
and byte-count metadata; its underlying format remains unparsed. The audit
used aggregate counts only and did not upload message or attachment content.

## Implemented boundary

`parser_key="nested_email"` (implementation:
`_parse_nested_email_metadata`) records sanitized headers and an attachment
count for one bounded nested message. `message.walk()` traverses the already
parsed MIME descendants for attachment counting, including descendants of an
attached `message/rfc822`; the parser does not recursively import or execute
nested messages. Byte and nested-message depth budgets fail closed before the
metadata result is retained.
`audio_metadata` validates only bounded MP3 ID3/frame signatures. The
`legacy_office_metadata` parser validates only the OLE/Compound File signature
for `.doc`. None of these paths decodes or executes untrusted content.

`parser_key="binary_metadata"` handles generic MIME attachments with only
`media_type` and `bytes` metadata when no recognized format signature exists. It
does not guess a format, decode bytes, or retain raw payload content. A
non-generic unidentified MIME remains explicit `unsupported_content_type`.

## Verification

- `backend/tests/test_attachment_parser.py` covers nested `.eml`, MP3 ID3,
  malformed MP3, legacy DOC OLE signatures, malformed DOC, and generic binary
  metadata including a payload over 20 MiB.
- Valid metadata returns `parse_status=parsed` and `parse_content_type=text/plain`;
  malformed input returns a named failure without raw bytes. PDF size and
  sidecar availability remain in the separate deferred recognition workflow.
- ADR-0011 fixes the non-recursive, non-decoding, and no-external-upload
  boundary for nested/media/legacy metadata; ADR-0012 fixes the generic
  binary metadata-only boundary.

## References (APA 7th)

Internet Engineering Task Force. (2008). *Internet message format (RFC 5322).*
https://www.rfc-editor.org/rfc/rfc5322

RFC 5322 defines the bounded header/body syntax used for one nested-message
inspection without recursive import.

Nilsson, M. (2000). *ID3 tag version 2.4.0—Main structure.* ID3.org.
https://id3.org/id3v2.4.0-structure

The ID3 specification supports the bounded ID3v2 header and synchsafe-size
check; this record does not decode audio or persist tag frames.

Microsoft. (2023). *[MS-CFB]: Compound File Binary File Format.* Microsoft
Open Specifications.
https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/53989ce4-7b05-4f8d-829b-d08d6148375b

MS-CFB supports signature-only legacy `.doc` recognition; no compound-file
streams or macros are traversed.
