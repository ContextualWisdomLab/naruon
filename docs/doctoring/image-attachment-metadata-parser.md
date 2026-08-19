# Image attachment metadata parser doctoring record

## Evidence

The 2026-07-31 pre-parser audit of the private local Inbox-backup snapshot
parsed 2,539 EML messages without parser exceptions. It found 2,056
attachments, including 1,438 PNG, 162 JPEG, 5 GIF, and 1 BMP attachments
classified as unsupported. A 2026-08-19 follow-up re-read the same immutable
local snapshot, so the population counts are intentionally identical while the
parser classifications changed. Neither audit uploaded message or attachment
content to an external service.

## Implemented boundary

`services.attachment_parser.image_metadata` reads bounded image headers with
the Python standard library and emits only `format`, `width`, `height`, and
`animated` metadata as searchable plain text. It does not decode pixels, retain
raw bytes, or perform OCR/object detection. Invalid and oversized payloads
remain visible as explicit failure states.

## Verification

- `backend/tests/test_attachment_parser.py` covers PNG, JPEG, GIF, BMP, generic
  MIME fallback, invalid payloads, and manifest registration.
- The existing import path passes the generated metadata through attachment
  embeddings and the content graph because the parser returns
  `parse_status=parsed` and `parse_content_type=text/plain`.
- ADR-0009 fixes the no-external-upload and local-sidecar boundary.

## References (APA 7th)

International Telecommunication Union. (1992). *Information technology—Digital
compression and coding of continuous-tone still images—Requirements and
guidelines (Recommendation ITU-T T.81).* https://www.itu.int/rec/T-REC-T.81

Microsoft. (2022). *Bitmap storage.* Microsoft Learn.
https://learn.microsoft.com/en-us/windows/win32/gdi/bitmap-storage

World Wide Web Consortium. (2025). *Portable Network Graphics (PNG)
specification (Third Edition).* https://www.w3.org/TR/png-3/

CompuServe Incorporated. (1990). *Graphics Interchange Format version 89a.*
https://giflib.sourceforge.net/gifstandard/GIF89a.html
