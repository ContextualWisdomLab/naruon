# Attachment parser boundary evidence

## Decision

Naruon accepts only explicitly registered inline attachment parsers. Unknown
or binary formats remain visible as metadata with
`parser_key=unsupported_binary` and `parse_status=unsupported_content_type`.
PDF recognition is deferred to NewsDOM, and oversized inline sources return
`parse_size_limit_exceeded` without raw parse content. The permanent decision
is [ADR-0005](../adr/0005-attachment-parser-boundary.md).

## Implementation and verification

- Manifest and fail-closed classification:
  `backend/services/attachment_parser.py`
- Import persistence and graph admission:
  `backend/services/email_import_service.py`
- Quality evidence and next-action surface:
  `backend/api/data.py` and `frontend/src/components/data-layout/QualityCheckTab.tsx`
- Realistic tests:
  `backend/tests/test_attachment_parser.py`,
  `backend/tests/test_email_import_service.py`, and
  `backend/tests/test_data_api.py`
- Required edge cases: generic MIME, unsupported PDF/binary, deferred PDF,
  one-million-character text, 20 MiB source, and metadata-only responses.

## Standards basis (APA 7th)

Freed, N., Klensin, J., & Hansen, T. (2013). *Media type specifications and
registration procedures* (RFC 6838). RFC Editor. https://doi.org/10.17487/RFC6838

Freed, N., & Borenstein, N. (1996). *Multipurpose Internet Mail Extensions
(MIME) part two: Media types* (RFC 2046). RFC Editor.
https://doi.org/10.17487/RFC2046

OWASP Foundation. (n.d.). *File upload cheat sheet*. OWASP Cheat Sheet Series.
https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## Maturity boundary

This evidence is attached to the feature PR and is not a claim that protected
`develop` has integrated the decision until the PR passes its hosted gates.
