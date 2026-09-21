# UI localization negotiation resource bounds

## Status and owned boundary

This record belongs to #1740's pure UI Localization Catalog policy. It does not add an HTTP route, persistence, browser cache, or a new transport error mapping. The purpose is to keep locale negotiation work bounded before later API owners expose the policy on a request path.

## Verified finding

The earlier policy bounded only RFC 9110 empty-list tolerance. Valid non-empty input remained attacker-controlled in three dimensions:

- an explicit persisted/session locale could contain an arbitrarily long syntactically valid basic language range;
- one `Accept-Language` field value could be arbitrarily long before normalization and comma splitting;
- one bounded-size field could still contain an unnecessarily large number of non-empty language ranges.

That leaves parser CPU/allocation proportional to unconstrained input. In particular, `candidate.split(",")` materializes the whole list after the raw string has already been accepted, so bounding only ignored empty members is not a complete resource boundary.

## RED and causal repair

RED `978fdbbc6135fa88a8d43e0971ed075ae546f9de` adds executable edges for inputs that were previously accepted:

- explicit locale length 128 characters is accepted and the next 9-character subtag is rejected with `ui_locale_input_invalid`;
- 64 non-empty `Accept-Language` members are accepted, while the 65th fails with `ui_accept_language_invalid`;
- an 8192-character syntactically valid `Accept-Language` range is accepted, while extending it by another 9-character subtag fails with `ui_accept_language_invalid`.

Causal fix `0fdb5371eef63d6d7abe87ac14b69269c8519ff8` introduces explicit product limits before expensive normalization/list processing:

- `_MAX_LOCALE_TAG_CHARS = 128`;
- `_MAX_ACCEPT_LANGUAGE_CHARS = 8192`;
- `_MAX_ACCEPT_LANGUAGE_MEMBERS = 64`;
- the existing `_MAX_ACCEPT_LANGUAGE_EMPTY_MEMBERS = 32` remains unchanged.

The policy rejects over-limit values; it never truncates them. The 128/8192/64 values are Naruon product limits, not IETF constants. They are intentionally explicit so later transport, observability, load-test, and security evidence can verify the same boundary instead of relying on framework defaults.

## Standards rationale

RFC 9110 §5.4 does not define a universal field-size limit. It explicitly allows a server to refuse a request field value larger than it is willing to process and requires an appropriate 4xx response rather than silently ignoring an oversized request field. The future HTTP owner must map the stable policy failure consistently with that transport contract; this pure-policy slice does not choose the endpoint/status code.

RFC 4647 §4.4 allows language-range length restrictions comparable to language-tag restrictions. RFC 5646 §4.4.1 states that implementations may refuse language tags above a specified length, requires such limits and their failure behavior to be documented, and requires limited-buffer protocols to support at least 35 characters. Naruon's 128-character explicit-locale budget exceeds that minimum and rejects rather than truncates.

The 8192-character `Accept-Language` value budget and 64 non-empty-member budget are application resource limits. They preserve ample interoperability headroom for ordinary preference lists while preventing one localization request from controlling unbounded split, regex, ranking, and duplicate-processing work. Outer HTTP servers/proxies may impose stricter limits; this policy does not weaken those boundaries.

## Rejected alternatives

Relying only on reverse-proxy, ASGI-server, or browser header limits is rejected because the pure policy is callable outside the eventual HTTP route and framework limits vary by deployment. Truncation is rejected because it can change language preference semantics. Bounding only empty list members is rejected because valid non-empty ranges and one very long range still leave work attacker-controlled.

## Verification boundary

The source and focused regression are committed. This automation environment does not contain an exact repository checkout, so no full-suite/local-container PASS is claimed here. Hosted checks and qualifying independent review must be reacquired on the final exact head after this documentation commit. Future HTTP/k6 evidence should additionally verify that an over-limit request is rejected before buyer-path work and that normal negotiation remains within the product p95 budget.

## TRACEABILITY

Fielding, R. T., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

Phillips, A., & Davis, M. (2006). *Matching of language tags* (RFC 4647, BCP 47). RFC Editor. https://doi.org/10.17487/RFC4647

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (RFC 5646, BCP 47). RFC Editor. https://doi.org/10.17487/RFC5646
