# Non-PDF DOM Evidence Pack

This pack grounds the Naruon P0 work item
`ContextualWisdomLab/naruon#1021`: parse non-PDF formats into the existing
`content_graph` / KG substrate.

## Implementation Scope

The implemented slice keeps `backend/services/content_graph/` as an internal
Naruon package. It does not create a new repository, submodule, package, or
domain because the repo-local architecture note says extraction should wait
until the parser API, segment schema, failure taxonomy, and golden tests have
stabilized and at least a second consumer exists.

Formats covered in this slice:

- `text/html` - existing safe block DOM parser, backed by the WHATWG HTML
  Living Standard and RFC 2854 media type registration.
- `text/markdown`, `text/x-markdown`, `application/markdown` - existing heading
  and paragraph parser, backed by CommonMark 0.31.2 and RFC 7763.
- `text/plain` - existing paragraph parser.
- `application/json`, `text/json`, and `+json` structured media types - new
  object/array/value segment parser.
- `text/csv`, `application/csv` - new row segment parser using RFC 4180-style
  rows and optional header treatment.
- `application/xml`, `text/xml`, and `+xml` structured media types - new
  `defusedxml` element-text parser following RFC 7303 media type boundaries.
- `text/calendar` - new property segment parser with RFC 5545 folded-line
  unfolding; RFC 9073 is preserved as the current event-publishing extension
  reference.

Unsupported binary formats still remain unsupported instead of being treated as
successful empty analysis.

## Preserved PDF Originals

- `pdfs/whatwg-html-living-standard-2026-07-10.pdf`
  - Source: https://html.spec.whatwg.org/print.pdf
  - Use: latest checked HTML Living Standard PDF, including DOM and parsing
    context for safe HTML block extraction.
- `pdfs/peters-lecocq-2013-content-extraction-using-diverse-feature-sets.pdf`
  - Source: https://archives.iw3c2.org/www2013/companion/p89.pdf
  - Use: research grounding for treating document extraction as block-level
    content extraction rather than raw blob storage.
- `pdfs/bevendorff-2023-empirical-comparison-web-content-extraction-algorithms.pdf`
  - Source: https://downloads.webis.de/publications/papers/bevendorff_2023c.pdf
  - Use: research grounding for keeping extraction evidence-oriented and
    benchmarkable before promoting it to a standalone product.

## Preserved Standard Text Originals

RFC Editor and CommonMark publish these references primarily as text or HTML;
official RFC PDF endpoints were not available through RFC Editor for these
documents at capture time, so the original text forms are preserved instead of
generating derivative PDFs.

- `standards/commonmark-0.31.2-spec.txt`
  - Source: https://spec.commonmark.org/0.31.2/spec.txt
- `standards/rfc2854-text-html.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc2854.txt
- `standards/rfc4180-csv.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc4180.txt
- `standards/rfc5545-icalendar.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc5545.txt
- `standards/rfc7303-xml-media-types.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc7303.txt
- `standards/rfc7763-text-markdown.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc7763.txt
- `standards/rfc8259-json.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc8259.txt
- `standards/rfc9073-icalendar-event-publishing-extensions.txt`
  - Source: https://www.rfc-editor.org/rfc/rfc9073.txt

## Governance Notes

- Project #1 item: `ContextualWisdomLab/naruon#1021`.
- Governing protocol: `ContextualWisdomLab/.github#363`.
- Restored planning file: `docs/planning/naruon-platform-plan.md`, because
  Project #1 and `.github#363` reference it as the roadmap detail source.
- Git LFS is intentionally not used; the largest committed PDF is about 16 MB.
