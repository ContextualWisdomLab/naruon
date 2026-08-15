# Email inline-media resolution evidence

## Scope and shipped-state boundary

This note traces the deterministic resolver implemented in `backend/services/email_media_resolution.py` on its active pull-request branch. It is **not protected-`develop` shipped truth until that pull request merges**. The bounded slice runs before OCR, object detection, multimodal reasoning, or semantic visual classification. It resolves local MIME evidence and produces content-addressed image candidates with exact occurrence provenance.

The resolver does not alter provider messages, fetch remote URLs, persist image payloads, or claim that a visual artifact is semantically relevant. Its `llm_safe` flag means only that the payload is within the configured byte bound, uses one of the admitted image media types, and its deterministic file signature agrees with the declared type. A downstream image decoder/model adapter must still perform its own decode and model-specific validation before inference.

## Standards-to-code trace

| Requirement | Primary basis | Naruon behavior |
| --- | --- | --- |
| Preserve MIME entity structure | RFC 2045; RFC 2046 | Traverse the parsed MIME tree and retain deterministic part paths. |
| Treat `multipart/related` as an aggregate | RFC 2387 | Resolve a `cid:` image only inside the nearest related scope; nested related entities create a new scope. |
| Convert `cid:` URLs to Content-ID evidence | RFC 2392 | Percent-decode the URL form, reject control/whitespace corruption, and match against normalized Content-ID header values. Duplicate matches fail closed as `review_required`. |
| Respect inline/attachment presentation metadata without using it as linkage authority | RFC 2183; RFC 2387 | Content-ID and related-container structure determine linkage; filename/disposition is not promoted to identity evidence. |
| Decode immediate `data:` media locally | RFC 2397 | Admit bounded base64 image data only for explicitly supported image media types; malformed or unsupported encodings remain unresolved evidence. |
| Do not create external side effects while parsing evidence | Security/product policy | HTTP(S) image references are recorded as `remote_blocked`; this resolver contains no network client or dereference path. |
| Preserve repeated visual occurrences | Product provenance contract | Image payloads are SHA-256 content-addressed while every MIME/HTML occurrence retains its own path/span. |

RFC 2387 has a verified technical erratum concerning the grammar of the required `type` parameter. Naruon does not attempt to re-implement that grammar; Python's MIME parser supplies the parsed tree, and the resolver uses the resulting `multipart/related` entity boundary.

## Deterministic safety boundary

The resolver enforces independent bounds for the raw message, individual image payloads, HTML text, extracted image references, and distinct content-addressed artifacts. Unsupported media, declared/signature mismatches, malformed base64, unresolved or ambiguous Content-ID references, and size-limit violations are explicit result states rather than silent omissions or model guesses.

A 1×1 PNG/GIF can be labelled `tracking_candidate` because dimensions are deterministic low-level evidence. That label is intentionally a candidate, not a finding that the sender used behavioral tracking. Logos, signatures, screenshots, charts, document scans, and table images remain `unclassified` until a later evidence-bound vision stage can make and explain those semantic distinctions.

## Verification evidence

The TDD branch began with the acceptance tests committed before the resolver. The focused local harness exercised realistic RFC 5322/MIME byte messages covering CID resolution, nested related-scope boundaries, duplicate Content-ID ambiguity, repeated identical signature-like images, base64 data images, remote no-fetch behavior, malformed references, unsupported media, MIME/signature mismatches, and resource limits. Owned production coverage for `services/email_media_resolution.py` was measured with branch coverage at **265/265 statements and 88/88 branches (100%)** before hosted repository checks; hosted exact-head CI remains authoritative for merge.

## References

Freed, N., & Borenstein, N. (1996a). *Multipurpose Internet Mail Extensions (MIME) Part One: Format of Internet Message Bodies* (RFC 2045). RFC Editor. https://doi.org/10.17487/RFC2045

Freed, N., & Borenstein, N. (1996b). *Multipurpose Internet Mail Extensions (MIME) Part Two: Media Types* (RFC 2046). RFC Editor. https://doi.org/10.17487/RFC2046

Levinson, E. (1998a). *The MIME Multipart/Related Content-type* (RFC 2387). RFC Editor. https://doi.org/10.17487/RFC2387

Levinson, E. (1998b). *Content-ID and Message-ID Uniform Resource Locators* (RFC 2392). RFC Editor. https://doi.org/10.17487/RFC2392

Masinter, L. (1998). *The "data" URL scheme* (RFC 2397). RFC Editor. https://doi.org/10.17487/RFC2397

Troost, R., Dorner, S., & Moore, K. (1997). *Communicating presentation information in Internet messages: The Content-Disposition header field* (RFC 2183). RFC Editor. https://doi.org/10.17487/RFC2183
