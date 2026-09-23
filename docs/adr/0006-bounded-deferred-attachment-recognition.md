# ADR-0006: Bounded deferred recognition for HWP and HWPX attachments

**Status:** Accepted (Naruon-local attachment import policy)
**Date:** 2026-08-20
**Decision owner:** Naruon maintainers
**Scope:** Email attachment classification and bounded deferred-recognition
workers. Import remains admission-only; HWPX extraction runs later in the
worker, while HWP binary conversion, OCR, and LLM processing remain separate.
**Figma File ID:** N/A — backend attachment admission; no visual surface.

## Context

Enterprise mailboxes contain HWP and HWPX documents that are not safely
represented by the generic unsupported-binary path. Dropping them loses
provenance; treating them as text can produce false content. The email import
transport already accepts bounded uploads above 20 MiB, so the parser must not
silently discard a valid deferred source below that transport ceiling.

## Decision

1. Classify `.hwp`, `.hwpx`, and `.owpml` extensions and their known media types
   as explicit parser families.
2. Admit HWP only when the bytes begin with the OLE Compound File signature and
   contain the HWP FileHeader identity marker. Admit HWPX only when a bounded,
   single-disk ZIP package has the exact `application/hwp+zip` mimetype and
   required package evidence.
3. Retain admitted source bytes as base64 deferred payloads, with a 64 MiB
   ceiling aligned with the email import transport. Reject invalid signatures,
   malformed ZIP metadata, unsupported ZIP structures, and over-limit payloads
   fail-closed with stable status codes.
4. Repeat format, path, compression, XML, resource, and expansion-ratio checks
   in the later sandboxed worker before extraction or conversion.
5. The worker extracts only canonical `Contents/sectionN.xml` HWPX members,
   rejects XML entity declarations and unsupported/encrypted compression, and
   records paragraph text plus stable content-graph provenance. HWP binary
   inputs remain pending until an independently sandboxed converter is wired.

## Consequences

- Buyers can see that HWP/HWPX input was recognized and is awaiting a safe
  worker, instead of seeing an opaque unsupported binary or losing the source.
- Large valid inputs up to 64 MiB preserve provenance, while bounded admission
  prevents unbounded memory and database payload growth.
- HWPX paragraph extraction is shipped as a bounded local worker capability.
  HWP binary conversion remains a separately auditable capability and is not
  claimed by this ADR.

## References (APA 7th)

Fielding, R., Nottingham, M., & Reschke, J. (Eds.). (2022). *HTTP semantics*
(RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

Hancom Inc. (n.d.). *HWP binary format and HWPML document format*. Hancom
Support. https://www.hancom.com/support/downloadCenter/hwpOwpml

PKWARE, Inc. (2024). *APPNOTE.TXT: .ZIP file format specification*.
https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT

World Wide Web Consortium. (2008, November 26). *Extensible Markup Language
(XML) 1.0 (Fifth Edition)*. https://www.w3.org/TR/xml/
