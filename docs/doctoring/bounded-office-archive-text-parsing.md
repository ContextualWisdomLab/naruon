# Bounded Office and ZIP attachment parsing doctoring record

## Evidence

The private local audit of the 2026-07-31 Inbox backup found 2,056
attachments. After image metadata coverage, the remaining dominant structured
families were OOXML/HWPX documents and ZIP archives. The audit read only the
local archive and recorded aggregate counts; no message or attachment content
was uploaded to an external service.

## Implemented boundary

`services.attachment_parser.office_text` opens only selected, bounded ZIP/XML
members for DOCX, XLSX, PPTX, and HWPX and emits searchable plain text. A
package larger than 20 MiB is still eligible when its selected XML fits the
128 MiB parser budget; embedded media is not read. It does not execute macros,
resolve external relationships, evaluate formulas, or render layouts. XML is
streamed with `iterparse` under aggregate limits of 1,000,000 elements and
100,000 extracted text parts, preventing a small XML member with excessive
node count from building an unbounded in-memory tree. The XML reader is the
repository's existing `defusedxml.ElementTree` implementation so untrusted
Office XML is not parsed through the unsafe standard-library XML surface.

`services.attachment_parser.archive_manifest` emits bounded ZIP member names
and declared sizes without extracting any member. Invalid input and archives
with more than 1,000 members fail closed without retaining raw bytes.

## Verification

- `backend/tests/test_attachment_parser.py` covers all four Office families,
  generic MIME extension fallback, malformed Office/ZIP input, ZIP manifests,
  calendar MIME aliases, vCards, and the existing unsupported-binary boundary.
- `backend/tests/test_email_import_service.py` verifies Office text reaches the
  attachment content graph.
- ADR-0010 fixes the no-execution, no-extraction, and no-external-upload
  boundary.

## References (APA 7th)

Ecma International. (2021). *ECMA-376: Office Open XML file formats* (5th ed.).
https://ecma-international.org/publications-and-standards/standards/ecma-376/

PKWARE. (n.d.). *.ZIP application note (APPNOTE).*
https://support.pkware.com/pkzip/appnote
