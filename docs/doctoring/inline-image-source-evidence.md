# Inline image source evidence doctoring record

## Implemented boundary

`services.inline_image_service` recognizes base64 image data URLs in HTML
`img[src]` elements and records their `html_dom_path`, MIME type, source
ordinal, SHA-256 digest, byte count, and bounded PNG/JPEG/GIF/BMP header facts.
The parser never stores the data URL or decoded bytes. The email import path
adds the bounded evidence to the email embedding input and writes a separate
`inline_image` content-graph source so search can find the image evidence
with a short ordinal display label. DOM paths are capped at 1,024 characters;
deeper paths retain a stable prefix and SHA-256 suffix so distinct source
locations do not collide in the normalized row. Oversized untrusted media-type
tokens fall back to a bounded `application/octet-stream` marker before
persistence. Before an embedding request, `redact_inline_image_payloads`
removes every `data:` URI from `img[src]`, including non-image media types, and
leaves only bounded searchable metadata.

The source UID is scoped by organization, user, message, ordinal, DOM locator,
and content digest, preventing equal message IDs from different tenants or
different image bytes from colliding in the global source identity.

## Failure and privacy boundary

Malformed data URLs, unsupported formats/encodings, invalid image headers, and
oversized decoded payloads remain explicit non-success states. OCR, object
detection, captions, safety labels, and image embeddings are not inferred from
metadata and are not sent to a hosted provider. A future local vision sidecar
must use the source digest and DOM locator as its provenance key.

## Verification

- `backend/tests/test_inline_image_service.py` covers valid metadata, stable
  sibling paths, deep-path persistence bounds, percent-escaped payloads,
  malformed input, unsupported input, non-data URLs, non-image data-URI
  redaction, and the size boundary.
- `backend/tests/test_email_parser.py` proves HTML EML parsing keeps the
  original MIME-part and DOM location.
- `backend/tests/test_inline_image_import_wiring.py` proves persistence and
  content-graph search wiring without a real mailbox dataset.
- `backend/alembic/versions/0018_inline_image_sources.py` adds the normalized
  source table without a raw payload column.

## References (APA 7th)

WHATWG. (n.d.). *Data URLs*. In *HTML Living Standard*. Retrieved August 21,
2026, from https://html.spec.whatwg.org/multipage/urls-and-fetching.html#data-urls

World Wide Web Consortium. (2025). *Portable Network Graphics (PNG)
specification (Third Edition).* https://www.w3.org/TR/png-3/

Huang, Y., Lv, T., Cui, L., Lu, Y., & Wei, F. (2022). LayoutLMv3:
Pre-training for document AI with unified text and image masking. *Proceedings
of the 30th ACM International Conference on Multimedia*, 4321–4330.
https://doi.org/10.1145/3503161.3548112
