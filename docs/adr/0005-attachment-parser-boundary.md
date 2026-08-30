# ADR-0005: Fail-closed attachment parser boundary

**Status:** Accepted (Naruon-local policy)
**Date:** 2026-08-24
**Decision owner:** Naruon maintainers
**Scope:** Email attachment import, deferred recognition, and customer-facing
attachment quality evidence.

## Context

An email `Content-Type` identifies a media type; it does not prove that
Naruon has a safe parser for the payload. Treating an unknown binary payload
as successfully parsed would create false knowledge-graph evidence and could
also retain more raw data than the customer needs. Attachment imports can
also exceed 20 MB, so inline parsing must be bounded independently of upload
transport limits.

## Decision

1. `backend/services/attachment_parser.py` is the source of truth for the
   parser manifest. Inline parsers are explicit for plain text, HTML,
   Markdown, JSON, CSV, XML, and iCalendar.
2. PDF is a declared deferred parser. It is persisted as
   `pdf_dom_recognition_pending` until the NewsDOM sidecar supplies recognized
   content; pending content is never reported as successfully parsed.
3. Unknown, generic, and binary content types are represented as
   `parser_key=unsupported_binary` and
   `parse_status=unsupported_content_type`. Their parse content and raw bytes
   are not promoted to the content graph or returned as user-facing body data.
4. Inline source processing is bounded at 20 MiB and one million characters.
   Oversized input returns `parse_size_limit_exceeded` metadata and no raw
   parse content.
5. The Email and Data surfaces show safe attachment metadata and a concrete
   parser-coverage next action. A new parser requires a manifest entry,
   security review, realistic import tests, and updated doctoring evidence.

## Consequences

- Customers can see that an attachment was received even when its format is
  unsupported, without a false empty parse result.
- Parser coverage gaps remain measurable through `parse_status` and
  `parser_key` quality evidence.
- PDF/DOCX/PPTX/XLSX support is not implied by a filename or MIME label; each
  format needs its own bounded adapter and regression evidence.
- The existing implementation is present on this feature branch/PR; protected
  `develop` integration and hosted checks remain governed by the normal PR
  process.

## References (APA 7th)

Freed, N., Klensin, J., & Hansen, T. (2013). *Media type specifications and
registration procedures* (RFC 6838). RFC Editor. https://doi.org/10.17487/RFC6838

Freed, N., & Borenstein, N. (1996). *Multipurpose Internet Mail Extensions
(MIME) part two: Media types* (RFC 2046). RFC Editor.
https://doi.org/10.17487/RFC2046

OWASP Foundation. (n.d.). *File upload cheat sheet*. OWASP Cheat Sheet Series.
https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
