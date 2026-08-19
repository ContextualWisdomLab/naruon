# ADR-0010: Bounded text and manifest parsing for Office and ZIP attachments

**Status:** Accepted (Naruon-local attachment parsing policy)
**Date:** 2026-08-19
**Decision owner:** Naruon maintainers
**Scope:** Email attachment ingestion and the content graph. This ADR does not
authorize external upload, macro execution, archive extraction, or provider
mutation.

## Context

The private local mailbox-backup audit found that the remaining unsupported
families after image metadata coverage were primarily OOXML/HWPX documents and
ZIP archives: 159 XLSX, 44 DOCX/HWPX, 24 PPTX, and 15 ZIP attachments. These
files are useful to search, but importing them through a general-purpose office
or archive runtime would expand the execution and data-retention boundary.

## Decision

1. Naruon registers an `office_text` parser for DOCX, XLSX, PPTX, and HWPX
   MIME/extension families. It reads only selected XML members from the ZIP
   package and emits bounded plain-text metadata plus extracted XML text.
2. Naruon registers an `archive_manifest` parser for ZIP attachments. It reads
   member names and declared uncompressed sizes only; it never extracts or
   executes archive members.
3. Both parsers use the Python standard library, enforce a 1,000-member limit,
   and reject malformed XML/ZIP data without retaining raw bytes. A large
   Office package is not rejected merely because embedded media makes the
   package exceed 20 MiB. Office text extraction applies a 128 MiB aggregate
   budget to selected-part declared sizes and bytes read, plus a 64-million
   character extracted-text ceiling; it returns `parse_size_limit_exceeded`
   when the selected XML safety budget or the 1,000-member archive limit is
   exceeded. Non-directory ZIP entries with traditional or strong-encryption
   flag bits (`0x01` or `0x40`) return the deterministic
   `encrypted_archive_entry` error. Valid output is
   `parse_status=parsed` and `parse_content_type=text/plain`, so the existing
   embedding and content-graph path indexes it. PDF retention is governed by
   the separate deferred NewsDOM workflow; this Office/ZIP ADR does not impose
   a PDF byte ceiling or reinterpret a sidecar rejection as an attachment
   parser type failure.
4. OOXML macro parts, relationships, arbitrary embedded objects, external
   links, encrypted packages, and unsupported XML parts are not interpreted.
   OCR, layout reconstruction, spreadsheet formula evaluation, and full office
   rendering remain deferred capabilities.
5. This ADR is the fixed local policy for these parser states. A future full
   document parser requires a new ADR or an explicit amendment with a new
   execution, retention, and provenance boundary.

## Alternatives rejected

### Execute a desktop office suite or archive extractor during import

Rejected because customer mailbox backups are confidential and import must not
execute untrusted attachment content or create an implicit external transfer.

### Add a new office/archive dependency for this first useful slice

Rejected because the safe searchable subset is available through the standard
library, while a full parser would add native code, larger supply-chain
surface, and a broader behavior contract before it is required.

### Keep all OOXML and ZIP attachments as unsupported binary

Rejected because the local audit shows these are common, structured formats for
which bounded text or manifest evidence is useful without decoding the full
document.

## Consequences

- Common Office attachments contribute searchable text and ZIP attachments
  contribute searchable member manifests through the existing graph path.
- Malformed, encrypted, or otherwise unselected content remains explicit as a
  parser failure or a bounded metadata-only result. Extremely large selected
  XML remains an explicit safety failure rather than silently truncating the
  searchable source.
- Existing unsupported rows are not silently rewritten; a future replay job
  must be separately authorized if operators want to backfill them.

## References (APA 7th)

Ecma International. (2021). *ECMA-376: Office Open XML file formats* (5th ed.).
https://ecma-international.org/publications-and-standards/standards/ecma-376/

PKWARE. (n.d.). *.ZIP application note (APPNOTE).*
https://support.pkware.com/pkzip/appnote

Müller, J., Ising, F., Mainka, C., Mladenov, V., Schinzel, S., & Schwenk, J.
(2020). Office document security and privacy. *Proceedings of the 10th USENIX
Workshop on Offensive Technologies (WOOT '20).* https://www.usenix.org/conference/woot20/presentation/muller

This study treats OOXML and ODF as ZIP/XML containers and documents denial of
service, encryption, active-content, and data-disclosure risks in legitimate
office features. It supports this ADR's narrow selected-part parser, aggregate
decompression budget, encrypted-entry rejection, and non-execution boundary;
it does not justify a malware-detection claim for Naruon's metadata parser.
