# HWP and HWPX attachment-recognition boundary

## Decision

Naruon recognizes HWPX and HWP attachments before OCR, XML extraction, or LLM
processing. The importer does not parse document semantics inline. It only
classifies the parser family, applies bounded signature checks, retains exact
source bytes as a base64 deferred-recognition payload, and records a stable
pending or rejection status.

This keeps email import deterministic and evidence-preserving while later
sandboxed workers perform heavier extraction.

## Shipped boundary

- `.hwpx` and `.owpml` files with generic binary MIME types are resolved to the
  HWPX parser family.
- HWPX content types are recognized as deferred OWPML XML packages.
- HWPX bytes must be a ZIP container with bounded metadata that identifies an
  HWPX-like package structure. Import inspects ZIP file names only; it does not
  decompress sections, execute active content, or fetch external resources.
- `.hwp` files with generic binary MIME types are resolved to the HWP parser
  family.
- HWP bytes must carry the OLE Compound File binary signature before the file can
  enter the sandboxed conversion queue.
- PDF behavior stays backward-compatible: callers that omit an expected content
  type from `decode_deferred_attachment_payload()` still get PDF validation.
- Invalid HWPX/HWP/PDF payloads fail closed and are not retained as deferred
  parser inputs.

## Status codes

| Parser family | Pending status | Rejection status |
| --- | --- | --- |
| PDF | `pdf_dom_recognition_pending` | `invalid_pdf_payload` |
| HWPX | `hwpx_xml_package_pending` | `invalid_hwpx_payload` |
| HWP | `hwp_conversion_pending` | `invalid_hwp_payload` |

## Out of scope

This slice does not implement semantic HWPX section extraction, embedded image
recognition, table reconstruction, HWP binary conversion, OCR, or LLM/VLM
interpretation. Those belong to a later worker-backed pipeline from the
evidence-based workspace epic.

## Safety and buyer value

Korean enterprise mailboxes often carry HWP and HWPX evidence. Treating those
attachments as opaque unsupported binaries breaks context synthesis, search
coverage, and auditability. Treating them as text or passing them directly to an
LLM is also unsafe. This slice gives the product an auditable middle state: the
source bytes are preserved, the file family is explicit, and follow-on workers
can proceed without losing provenance.

## References

Hancom Inc. (n.d.). *HWP binary format and HWPML document format*. Hancom Support.
https://www.hancom.com/support/downloadCenter/hwpOwpml

Hancom Inc. (n.d.). *Hancom SDK: HWP/HWPX document processing development kit*.
Hancom SDK. https://sdk.hancom.com/sdks/1

Hancom Tech. (n.d.). *HWPX format*. https://tech.hancom.com/hwpxformat/

PKWARE, Inc. (2024). *APPNOTE.TXT: .ZIP file format specification*.
https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
