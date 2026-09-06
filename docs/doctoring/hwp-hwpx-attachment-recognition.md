# HWP and HWPX attachment-recognition boundary

## Decision

Naruon recognizes HWPX and HWP attachments before OCR, XML extraction, or LLM
processing. The importer does not parse document semantics inline. It only
classifies the parser family, applies bounded signature checks, retains exact
source bytes as a base64 deferred-recognition payload, and records a stable
pending or rejection status.

This keeps email import deterministic and evidence-preserving while later
sandboxed workers perform heavier extraction.

## Active deferred-import boundary — PR #1353

- `.hwpx` and `.owpml` files with generic binary MIME types are resolved to the
  HWPX parser family.
- HWPX content types are recognized as deferred OWPML XML packages.
- HWPX bytes must be a bounded single-disk ZIP package with one unambiguous
  `mimetype` member whose exact content is `application/hwp+zip`, a `version.xml`
  member, and at least one canonical `Contents/sectionN.xml` member. Package
  manifest presence alone is not sufficient admission evidence because the
  recognition worker cannot materialize a sectionless package.
- The importer validates the end-of-central-directory entry count and directory
  size before Python materializes ZIP members, then bounds aggregate member-name
  bytes and the tiny `mimetype` payload before reading it.
- Duplicate `mimetype` members, wrong signature text, encrypted signature
  members, unsupported ZIP structures, malformed ZIP metadata, sectionless
  packages, and exceeded limits fail closed as `invalid_hwpx_payload`.
- Import does not decompress document sections, extract files, execute active
  content, or fetch external resources. Later workers must repeat path,
  compression, XML, resource, and expansion-ratio validation before extraction.
- `.hwp` files with generic binary MIME types are resolved to the HWP parser
  family.
- HWP bytes must carry both the OLE Compound File container signature and the
  HWP FileHeader identity marker `HWP Document File` before the file can enter
  the sandboxed conversion queue. OLE magic by itself is not HWP authority.
- The low-cost identity check does not prove CFB directory integrity, stream
  ownership, encryption state, record validity, or safe convertibility; the
  sandboxed HWP worker must parse and validate those structures again.
- PDF behavior stays backward-compatible: callers that omit an expected content
  type from `decode_deferred_attachment_payload()` still get PDF validation.
- Invalid HWPX/HWP/PDF payloads fail closed and are not retained as deferred
  parser inputs.
- The recognition worker reads only canonical `Contents/sectionN.xml` members,
  bounds each section and the aggregate XML bytes, rejects entity declarations,
  and lands paragraph text with stable content-graph provenance. The worker
  never executes package content or follows external resources.

## HWPX resource bounds

| Boundary | Current import limit | Purpose |
| --- | ---: | --- |
| Complete deferred source | 64 MiB | Align deferred retention with the email import transport while bounding memory and database payload growth. |
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
the HWPX signature, while a small source file could still devote most of its
bytes to a very large central directory.

Commit `4b51240eb8521459ef622e49bd463a1a6d783288` added failing public-boundary
regressions for wrong and duplicate `mimetype` members, entry count,
central-directory bytes, aggregate name bytes, and signature-member bytes.
Commit `b737ae83c94ee8a5aaf9c22a8239056e26ffe029` then implemented the bounded
end-of-central-directory preflight and exact signature validation.

A later review found that import admission still accepted a package with a
manifest but no section XML, while the recognition worker must reject that same
package because there is no materializable `Contents/sectionN.xml`. RED commit
`44a268b988f9a3092368bd774a26582647e319a9` adds the manifest-only regression;
causal fix `4281904b438ac50c2d6c40d14207119c383227a8` requires section evidence at
import admission so the queue and worker share one fail-closed boundary.

The initial HWP slice likewise admitted any OLE Compound File if the caller
supplied an HWP extension or media type. Commit
`d97281ce7f452a10b0a5c76718d37d126958a4ae` added regressions proving that an
unrelated OLE container must fail both import-time and deferred-decoder checks.
Commit `07bd3b30abe483b50129653a4fd599f7ddc9488d` then required the published HWP
FileHeader identity marker as a second admission signal; commit
`c8837fb00d74bd4ddc3152e0fe793e71f9e1f41f` aligned the positive fixture with
that real contract.

Hosted exact-head CI, security, coverage, and review evidence remains
authoritative for merge.

## Status codes

| Parser family | Pending status | Rejection status |
| --- | --- | --- |
| PDF | `pdf_dom_recognition_pending` | `invalid_pdf_payload` |
| HWPX | `hwpx_xml_package_pending` | `invalid_hwpx_payload` |
| HWP | `hwp_conversion_pending` | `invalid_hwp_payload` |

## Out of scope

This slice does not implement embedded image recognition, table reconstruction,
HWP binary conversion, OCR, or LLM/VLM interpretation. HWPX paragraph
extraction is implemented in the bounded worker; richer layout reconstruction
belongs to a later worker-backed pipeline from the evidence-based workspace
epic.

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

Hancom Tech. (2025a, February 24). *HWP format structure*.
https://tech.hancom.com/%ED%95%9C-%EA%B8%80-%EB%AC%B8%EC%84%9C-%ED%8C%8C%EC%9D%BC-%ED%98%95%EC%8B%9D-hwp-%ED%8F%AC%EB%A7%B7-%EA%B5%AC%EC%A1%B0-%EC%82%B4%ED%8E%B4%EB%B3%B4%EA%B8%B0/

Hancom Tech. (2025b, February 26). *HWPX format structure*.
https://tech.hancom.com/hwpxformat/

PKWARE, Inc. (2024). *APPNOTE.TXT: .ZIP file format specification*.
https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT

Fielding, R., Nottingham, M., & Reschke, J. (Eds.). (2022). *HTTP semantics*
(RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

World Wide Web Consortium. (2008, November 26). *Extensible Markup Language
(XML) 1.0 (Fifth Edition)*. https://www.w3.org/TR/xml/
