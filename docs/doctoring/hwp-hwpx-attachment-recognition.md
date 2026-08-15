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
- HWPX bytes must be a bounded single-disk ZIP package with one unambiguous
  `mimetype` member whose exact content is `application/hwp+zip`, a `version.xml`
  member, and either package-manifest or section evidence.
- The importer validates the end-of-central-directory entry count and directory
  size before Python materializes ZIP members, then bounds aggregate member-name
  bytes and the tiny `mimetype` payload before reading it.
- Duplicate `mimetype` members, wrong signature text, encrypted signature
  members, unsupported ZIP structures, malformed ZIP metadata, and exceeded
  limits fail closed as `invalid_hwpx_payload`.
- Import does not decompress document sections, extract files, execute active
  content, or fetch external resources. Later workers must repeat path,
  compression, XML, resource, and expansion-ratio validation before extraction.
- `.hwp` files with generic binary MIME types are resolved to the HWP parser
  family.
- HWP bytes must carry the OLE Compound File binary signature before the file can
  enter the sandboxed conversion queue.
- PDF behavior stays backward-compatible: callers that omit an expected content
  type from `decode_deferred_attachment_payload()` still get PDF validation.
- Invalid HWPX/HWP/PDF payloads fail closed and are not retained as deferred
  parser inputs.

## HWPX resource bounds

| Boundary | Current import limit | Purpose |
| --- | ---: | --- |
| Complete deferred source | 20 MiB | Prevent oversized payload retention. |
| ZIP entry count | 4,096 | Bound member-object and traversal work. |
| Central-directory bytes | 4 MiB | Bound metadata parsing before member materialization. |
| Aggregate decoded member-name bytes | 1 MiB | Prevent path/name metadata amplification. |
| `mimetype` uncompressed bytes | 128 bytes | Keep signature validation deterministic and non-expansive. |

These are admission limits, not statements about the maximum document Hancom
Office can create. An operator may change them only with reviewed capacity and
security evidence. The recognition step deliberately rejects ZIP64 or multi-disk
packages rather than widening a low-cost email-import boundary.

## Test-first repair evidence

The initial HWPX slice accepted a ZIP by member names alone. A generic ZIP could
therefore imitate `mimetype`, `version.xml`, and section paths without carrying
the HWPX signature, while a small source file could devote most of its bytes to a
very large central directory.

Commit `4b51240eb8521459ef622e49bd463a1a6d783288` added failing public-boundary
regressions for wrong and duplicate `mimetype` members, entry count,
central-directory bytes, aggregate name bytes, and signature-member bytes.
Commit `b737ae83c94ee8a5aaf9c22a8239056e26ffe029` then implemented the bounded
end-of-central-directory preflight and exact signature validation. Hosted
exact-head CI, security, coverage, and review evidence remains authoritative for
merge.

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
