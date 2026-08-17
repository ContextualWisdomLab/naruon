# Email inline-media admission evidence

## Scope and shipped-state boundary

This note traces the deterministic admission classifier in
`backend/services/email_media_admission.py`. It is **#1350 Slice 3 admission
only** and is **not protected-`develop` shipped truth until the pull request
merges**. The slice runs before OCR, vision-language models, NewsDOM, or any
LLM. It does not mutate provider mail, does not blanket-mask business PII, and
does not add a remote-image egress path.

Predecessor evidence is **N/A**. Open PR #1376 already covers
`EmailMediaArtifact` pixel-dimension extraction on a separate branch; that
contract is **not** on protected `develop` and is not copied or rewritten here.
This module reads PNG IHDR and GIF logical-screen sizes only as a local
tracking-pixel heuristic.

## Buyer-visible contract

Naruon must not send a 1×1 beacon to a model or treat it as document evidence.
Admission therefore:

1. Resolves `cid:` URLs against Content-ID values inside the same message's
   `multipart/related` entity (RFC 2392; RFC 2046). A missing, malformed, or
   ambiguous target fails closed with `unresolved_cid_reference`.
2. Classifies admitted local images into the closed set `tracking_pixel`,
   `unsupported_media`, and `document_image`. Screenshots, charts, and scans
   share `document_image` in this slice.
3. Labels tracking pixels from local evidence only: tiny header-derived
   dimensions (1×1), typical tracker content-types on tiny GIF payloads, and
   known tracker hosts or paths on an already-present `Content-Location`
   header. Remote pixels are never downloaded.
4. Returns provenance: source part index, Content-ID, SHA-256 of the exact
   decoded source bytes, classification, and `known` / `unknown` evidence
   boundary. Repeated identical base64 parts share one hash and keep distinct
   part indexes.

`http` and `https` image references remain recorded as no-fetch
(`remote_fetch_policy=disabled`). They are not admitted as document images.

## Resolution wiring boundary

Admission alone does not stop a later parse or OCR step from treating a
classified beacon as document input. `services.email_media_resolution`
therefore calls `admit_email_inline_media()` first. Only `document_image`
admissions continue. `tracking_pixel`, `unsupported_media`, and
`unresolved_cid_reference` are quarantined with those stable error_codes and
are dropped from filename-bearing image attachments on the existing
`parse_eml` / `parse_eml_bytes` path. This wiring does not add OCR, a VLM,
NewsDOM, egress, or the #1376 `EmailMediaArtifact` pixel contract.

Customer next action: send only `document_image` continuations downstream.
Do not send a tracker, unsupported part, or unresolved CID to a model.

## Standards-to-code trace

| Requirement | Primary basis | Naruon behavior |
| --- | --- | --- |
| Preserve MIME entity structure and media types | RFC 2045; RFC 2046 | Walk the parsed MIME tree, retain leaf part indexes, and classify from declared type plus file signature. |
| Treat related body parts as one aggregate | RFC 2046 multipart composite media types | Bind `cid:` only inside the nearest `multipart/related` scope. |
| Convert `cid:` URLs to Content-ID tokens | RFC 2392 | Percent-decode the URL form, reject control or whitespace corruption, and match stripped Content-ID headers. Duplicate matches fail closed. |
| Do not create external side effects while admitting evidence | Product/security policy; Englehardt et al. (2018) | No HTTP client. Tracker URL patterns are applied only to headers already present on the local part. |

## Academic summary (PDF not attached)

Englehardt, Han, and Narayanan (2018) measured commercial mailing-list mail
and showed that viewing a message commonly loads third-party embedded pixels
that leak recipient identity. About 30% of their corpus leaked the recipient
address to one or more third parties on view. The paper is published under
Creative Commons Attribution-NonCommercial-NoDerivs 3.0, so this repository
cites and summarizes it rather than redistributing the PDF.

Naruon uses that finding as the buyer reason to keep 1×1 and tracker-header
images out of OCR/VLM admission. The paper's proposed client-side stripping of
remote tracking tags is **not** implemented here; this slice only refuses to
treat those local beacons as document evidence and refuses to fetch remote
ones.

## Verification

Focused product tests cover four realistic `.eml` fixtures: a resolving CID
chart, an unresolved CID, a 1×1 GIF with a Mailchimp-style Content-Location,
and two identical base64 PNG parts that share one SHA-256. Boundary tests
cover unsupported media, remote no-fetch, ambiguous Content-ID, and helper
fail-closed paths. The wiring tests prove a named 1×1 CID tracker and an
unresolved CID do not continue as document evidence on `parse_eml_bytes`,
while a resolving CID chart does. Owned admission and resolution module
statement and branch coverage is 100% on the focused harness.

## References

Englehardt, S., Han, J., & Narayanan, A. (2018). I never signed up for this!
Privacy implications of email tracking. *Proceedings on Privacy Enhancing
Technologies, 2018*(1), 109–126. https://doi.org/10.1515/popets-2018-0006

Freed, N., & Borenstein, N. (1996a). *Multipurpose Internet Mail Extensions
(MIME) Part One: Format of Internet Message Bodies* (RFC 2045). RFC Editor.
https://doi.org/10.17487/RFC2045

Freed, N., & Borenstein, N. (1996b). *Multipurpose Internet Mail Extensions
(MIME) Part Two: Media Types* (RFC 2046). RFC Editor.
https://doi.org/10.17487/RFC2046

Levinson, E. (1998). *Content-ID and Message-ID Uniform Resource Locators*
(RFC 2392). RFC Editor. https://doi.org/10.17487/RFC2392
