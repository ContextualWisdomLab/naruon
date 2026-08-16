# HWP and HWPX attachment-recognition boundary

## Status

This document separates protected-`develop` truth from active pull-request work.
The HWP/HWPX deferred-import contract is owned by active parent PR #1353. The
ordered HWPX section recognizer and its production worker handoff are owned by
stacked active PR #1373. Neither capability is shipped from protected `develop`
until its exact integrated head passes the live review, CI, security, coverage,
provenance, and branch-governance gates and is merged.

## Decision

Naruon recognizes HWPX and HWP attachments before OCR, XML extraction, or LLM
processing. The importer does not parse document semantics inline. It only
classifies the parser family, applies bounded signature checks, retains exact
source bytes as a base64 deferred-recognition payload, and records a stable
pending or rejection status.

The HWPX worker then performs a deterministic local recognition stage rather
than sending package bytes to an external model or NewsDOM provider. It repeats
package validation, resolves body sections through `Contents/content.hpf`,
parses only bounded selected XML with entity/DTD defenses, and lands ordered
paragraph text plus source-bound content-graph provenance. This keeps email
import deterministic and evidence-preserving while making recognized Korean
enterprise document text searchable without model dependence.

## Active deferred-import boundary — PR #1353

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
  content, or fetch external resources. Later workers repeat path, XML,
  encryption, resource, and expansion validation before extraction.
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

## Active HWPX semantic-recognition boundary — PR #1373

The current bounded vertical slice consumes only `hwpx_xml_package_pending`
email attachments. It reuses Naruon's existing leased background-recognition
worker instead of creating another scheduler or service authority.

1. The worker decodes the retained base64 bytes with the HWPX content-family
   validator. Corrupted or family-mismatched retained payloads become
   `hwpx_xml_package_failed` with `invalid_pending_payload` before XML parsing.
2. `mimetype` and `Contents/content.hpf` are mandatory. The worker rejects
   duplicate paths, encrypted entries, traversal paths, unsafe manifest hrefs,
   unresolved or repeated spine targets, and XML that violates the defused
   parser boundary.
3. Manifest identity resolves each spine item and the spine defines section
   reading order. Only `Contents/sectionN.xml` targets are accepted in this
   slice.
4. Each selected XML member is bounded before decompression/read, and the
   selected `content.hpf` plus section XML expansion total is bounded.
5. Paragraphs are emitted in section/document order into the existing content
   graph. The graph UIDs remain bound to SHA-256 of the exact original HWPX
   source bytes rather than a lossy text reserialization.
6. Recognition succeeds without a NewsDOM/provider configuration. Provider
   resolution and network calls remain PDF-only behavior.
7. Orphan attachments and parser failures remain visible failure states; no
   error path is reported as parsed.
8. The production sweep selects PDF and HWPX pending rows together with the
   existing bounded, cursor-based, leased batch semantics so an HWPX attachment
   cannot remain permanently invisible to the running worker.

This slice deliberately reuses the existing `PdfDomSection`/`parse_pdf_dom`
graph construction primitive as a format-neutral document→section→paragraph
builder. That reuse does not assert that HWPX is PDF or transfer PDF parsing
semantics; the recognizer supplies HWPX-derived ordered sections and the exact
HWPX source hash.

## Standards confirmation

The Korean national standards registry identifies KS X 6101, *Open
Word-Processor Markup Language (OWPML) document structure*, and records its
latest confirmation/revision date as 2024-10-30. Hancom's current format
material states that HWPX follows KS X 6101/OWPML and is a ZIP-packaged XML
format designed for machine-readable document content. Hancom's HWPX parsing
guidance also maps body XML to the OWPML body/section/paragraph schemas. The
worker therefore treats package and XML structure as deterministic document
evidence, not as an LLM interpretation target.

No psychometric/statistical or model-orchestration claim is introduced by this
slice, so peer-reviewed model evidence is not a gating dependency here. The
material authority is the current national standard plus the format owner's
primary technical documentation.

## HWPX resource bounds

| Boundary | Current bound | Applied at | Purpose |
| --- | ---: | --- | --- |
| Complete deferred source | 20 MiB | import + deferred decode | Prevent oversized payload retention. |
| ZIP entry count | 4,096 | import + worker | Bound member-object and traversal work. |
| Central-directory bytes | 4 MiB | import | Bound metadata parsing before member materialization. |
| Aggregate decoded member-name bytes | 1 MiB | import + worker | Prevent path/name metadata amplification. |
| `mimetype` uncompressed bytes | 128 bytes | import + worker | Keep signature validation deterministic and non-expansive. |
| One selected XML member | 4 MiB | worker | Bound decompression and parser memory per selected member. |
| Selected XML total | 16 MiB | worker | Bound aggregate semantic-recognition expansion. |

These are product admission/worker limits, not statements about the maximum
document Hancom Office can create. An operator may change them only with
reviewed capacity and security evidence. The import boundary deliberately
rejects ZIP64 or multi-disk packages rather than widening low-cost email import.

## Test-first evidence

### Import hardening — parent PR #1353

The initial HWPX slice accepted a ZIP by member names alone. A generic ZIP could
therefore imitate HWPX paths without carrying the HWPX signature, while a small
source file could still devote most of its bytes to a very large central
directory.

Commit `4b51240eb8521459ef622e49bd463a1a6d783288` added failing public-boundary
regressions for wrong and duplicate `mimetype` members, entry count,
central-directory bytes, aggregate name bytes, and signature-member bytes.
Commit `b737ae83c94ee8a5aaf9c22a8239056e26ffe029` then implemented the bounded
end-of-central-directory preflight and exact signature validation.

The initial HWP slice likewise admitted any OLE Compound File if the caller
supplied an HWP extension or media type. Commit
`d97281ce7f452a10b0a5c76718d37d126958a4ae` added regressions proving that an
unrelated OLE container must fail both import-time and deferred-decoder checks.
Commit `07bd3b30abe483b50129653a4fd599f7ddc9488d` then required the published HWP
FileHeader identity marker as a second admission signal; commit
`c8837fb00d74bd4ddc3152e0fe793e71f9e1f41f` aligned the positive fixture with
that real contract.

### Ordered recognition and worker handoff — PR #1373

- `84662ac7cf359455c59d37b54f201133558e9097` specifies OPF-spine ordering,
  path/provenance, package traversal, XML expansion, unsafe-XML, and unresolved
  spine behavior before the recognizer exists.
- `66d3fd336c1cfaf37691e238c8ac3481b7eb2d56` implements the bounded HWPX
  recognizer.
- `ef8e990f2a88c861bd0f9135861e040a30aff8cc` specifies the production worker
  handoff: local recognition without a provider, retained-byte revalidation,
  failure visibility, content-graph landing, and pending-row selection.
- `944a5303b814171b1f12553d9fe45d75a416440c` wires the HWPX pending state into
  the existing leased recognition worker and preserves the PDF path.
- `fdf157dd675f8ca91a248f801c2c6e4c75e0732f` and
  `fbc7b4637e31ddf421af4aa5d2d94ae24e970e9f` cover parser-family orphan status
  and canonical MIME fallback branches.

Hosted exact-head CI, security, coverage, and review evidence remains
authoritative for merge; the commit lineage above is implementation
traceability, not a substitute for current-head gates.

## Requirement traceability

| Requirement | Production owner | Test evidence | Maturity |
| --- | --- | --- | --- |
| Bounded HWPX admission and exact source retention | `backend/services/attachment_parser.py` | `test_attachment_parser*.py` | Active parent PR #1353 |
| OPF manifest/spine ordered HWPX paragraph recognition | `backend/services/hwpx_recognition.py` | `test_hwpx_recognition.py` | Active stacked PR #1373 |
| Deferred HWPX worker selection and local execution | `backend/services/newsdom_worker.py` | `test_hwpx_worker.py` | Active stacked PR #1373 |
| Parsed attachment text + graph provenance | shared content-graph landing path | HWPX worker + recognizer tests | Active stacked PR #1373 |
| Binary HWP conversion | future sandboxed converter | none yet | Planned / out of this slice |
| HWPX tables, images, layout fidelity | future bounded recognizers | none yet | Planned / out of this slice |
| Protected-`develop` shipped HWP/HWPX recognition | protected branch | integrated release gates | Not yet shipped |

## Status codes

| Parser family | Pending status | Parsed/failed state |
| --- | --- | --- |
| PDF | `pdf_dom_recognition_pending` | existing NewsDOM parsed/failed states |
| HWPX | `hwpx_xml_package_pending` | `hwpx_xml_package_parsed` / `hwpx_xml_package_failed` |
| HWP | `hwp_conversion_pending` | converter not implemented in this slice |

## Out of scope

This slice does not reconstruct HWPX tables, images, charts, layout, styles, or
embedded objects; convert binary HWP; perform OCR; fetch external resources; or
call LLM/VLM providers. Those require separately bounded workers and acceptance
evidence. The worker is not a general ZIP/XML extraction service.

## Safety and buyer value

Korean enterprise mailboxes often carry HWP and HWPX evidence. Treating those
attachments as opaque unsupported binaries breaks context synthesis, search
coverage, and auditability. Treating them as unbounded XML/ZIP input or passing
source bytes directly to an LLM is also unsafe. The active vertical slice gives
the product an auditable path from retained source bytes to ordered searchable
paragraphs and exact-source provenance while keeping failure states explicit.

## References

Korean Agency for Technology and Standards. (2024, October 30). *KS X 6101:
Open Word-Processor Markup Language (OWPML) document structure*. e-Nara Standard
Certification. https://www.standard.go.kr/KSCI/standardIntro/getStandardSearchView.do?ksNo=KSX6101&menuId=503&tmprKsNo=KSX6101&topMenuId=502

Hancom Inc. (n.d.). *HWP binary format and HWPML document format*. Hancom Support.
https://www.hancom.com/support/downloadCenter/hwpOwpml

Hancom Inc. (n.d.). *Hancom SDK: HWP/HWPX document processing development kit*.
Hancom SDK. https://sdk.hancom.com/sdks/1

Hancom Tech. (2025a, February 24). *HWP format structure*.
https://tech.hancom.com/%ED%95%9C-%EA%B8%80-%EB%AC%B8%EC%84%9C-%ED%8C%8C%EC%9D%BC-%ED%98%95%EC%8B%9D-hwp-%ED%8F%AC%EB%A7%B7-%EA%B5%AC%EC%A1%B0-%EC%82%B4%ED%8E%B4%EB%B3%B4%EA%B8%B0/

Hancom Tech. (2025b, February 26). *HWPX format structure*.
https://tech.hancom.com/hwpxformat/

Hancom Tech. (2025c). *Parsing HWPX format with Python (Part 1)*.
https://tech.hancom.com/python-hwpx-parsing-1/

Hancom Tech. (2025d). *Parsing HWPX format with Python (Part 2)*.
https://tech.hancom.com/python-hwpx-parsing-2/

PKWARE, Inc. (2024). *APPNOTE.TXT: .ZIP file format specification*.
https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
