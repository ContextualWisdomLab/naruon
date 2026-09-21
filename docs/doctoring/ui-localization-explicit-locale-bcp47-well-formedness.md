# UI localization explicit-locale BCP 47 well-formedness

Status: Proposed with PR #1740. This record covers the pure explicit-locale policy only; it does not change the broader RFC 4647 `Accept-Language` language-range grammar.

## Problem

`normalize_supported_locale()` originally used the broad pattern `[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*`. That shape was adequate to recover a primary language but was not the RFC 5646 `Language-Tag` grammar. It accepted malformed explicit preferences such as `en-x` and `en-u`: both have a supported primary language, but RFC 5646 requires private-use `x` to be followed by at least one private-use subtag and an extension singleton such as `u` to be followed by at least one 2-8 character extension subtag.

Accepting those values as persisted/session locale identities made the explicit preference boundary weaker than its own documentation and blurred two different standards surfaces: RFC 5646 language tags for explicit stored/session identities versus RFC 4647 basic language ranges used inside `Accept-Language`.

A second standards sweep found the first structural repair incomplete. RFC 5646 defines `Language-Tag = langtag / privateuse / grandfathered`; some grandfathered values are intentionally outside the `langtag` production, while regular grandfathered values may also look structurally like `langtag`. For the current release-primary set, `en-GB-oed`, `zh-min`, and `zh-min-nan` require recognition as complete fixed grandfathered tags before ordinary structural guards reinterpret apparent subtags. Other fixed grandfathered values remain syntactically well formed even when Naruon does not support their primary language.

A third sweep found a typed-boundary defect left by treating only supported-primary tags as syntactically relevant. RFC 5646 permits a language tag to consist entirely of private-use subtags, and grandfathered tags remain well-formed language tags. Values such as `x-private`, `i-klingon`, and `sgn-BE-FR` are therefore syntactically well-formed but do not map to one of Naruon's eight release primaries. They belong to `ui_locale_unsupported`, not `ui_locale_input_invalid`.

A later boundary sweep found a separate whitespace-normalization defect. The explicit persisted/session path called `locale_tag.strip(" ")` before RFC 5646 validation, so `" en-US"`, `"en-US "`, and `" en-US "` were silently accepted as `en-US`. RFC 5646 states that whitespace is not permitted in a language tag. That differs from the HTTP `Accept-Language` surface, where HTTP list syntax deliberately permits optional whitespace around field-value list elements. Explicit stored/session locale identity therefore must not borrow HTTP OWS normalization.

## RED

Commit `478bd95fdbd2b6601fae1ab70c3513abf0f985fe` adds focused cases that fail on the predecessor policy:

- `en-x` must fail with `ui_locale_input_invalid`;
- `en-u` must fail with `ui_locale_input_invalid`;
- `en-x-private` remains accepted and normalizes to `en`;
- `en-u-ca-gregory` remains accepted and normalizes to `en`.

Commit `8d9a0f67a47b26eb1e36a7bc65681470033c6f74` adds the grandfathered-tag regression:

- `en-GB-oed` normalizes to `en`;
- `zh-min` normalizes to `zh`;
- `zh-min-nan` normalizes to `zh`.

Commit `d23d4095d1c2ac8542f1ac247b6fee87fcb9485c` adds the syntax-versus-support classification regression:

- `x-private` is well-formed private-use-only syntax and must fail with `ui_locale_unsupported`;
- `i-klingon` is an irregular grandfathered language tag and must fail with `ui_locale_unsupported`;
- `sgn-BE-FR` is an irregular grandfathered language tag and must fail with `ui_locale_unsupported`.

Commit `2ff28c208b8fd5a83bee3e179f4d66b31831be43` adds the explicit-boundary whitespace regression:

- leading SP before `en-US` must fail with `ui_locale_input_invalid`;
- trailing SP after `en-US` must fail with `ui_locale_input_invalid`;
- leading and trailing SP together must fail with `ui_locale_input_invalid`.

The regressions are intentionally scoped to explicit locale values. They do not tighten RFC 4647 language-range parsing in `Accept-Language`, where the grammar and HTTP OWS boundary are different.

## Decision

Causal fix `3a87209306ad1b3dee67cb9e0e9e513dfb7a4f3a` replaces the permissive explicit-locale pattern with an RFC 5646 structural `langtag` pattern covering language/extlang, optional script and region, variants, extensions, and optional private-use suffix.

Follow-up causal fix `aceef1b282d948411fe9b04b8cd08750fcdacfe8` restored the supported-primary grandfathered forms `zh-min` and `zh-min-nan` alongside `en-GB-oed` without introducing a moving IANA-registry dependency.

Causal fix `dc077bec9ae47e1421fa678ae43451f65784c410` established separate admission branches for structural `langtag`, private-use-only tags, and the then-explicit fixed grandfathered exceptions before release support is evaluated. Only after a candidate is established as well-formed does the policy inspect the first subtag for membership in `ko/en/ja/zh/vi/es/de/fr`. This preserves the stable semantic distinction between malformed input and well-formed-but-unsupported input.

Current source repair `8666ef7bf2451f4e4ca8e93c69d24d5a9fb6436c` completes that boundary: both RFC 5646 regular and irregular grandfathered tags are recognized from the RFC's fixed list before ordinary `langtag` structural guards run. This matters for `zh-min-nan`, whose spelling also matches the structural pattern and would otherwise be misread as occupying two extlang positions. Fixed-grandfathered recognition establishes syntax only; unsupported primary languages still fail afterward as `ui_locale_unsupported`. Ordinary non-grandfathered `langtag` values continue through the multi-extlang, repeated-singleton, and duplicate-variant validity guards.

The complete regular+irregular grandfathered list is fixed by RFC 5646, so this admission exception does not create a moving registry dependency. Registry validity, Prefix relationships, deprecation, Preferred-Value replacement, and canonicalization beyond that fixed RFC list remain outside this pure policy until a dated/versioned IANA-registry contract exists.

Causal fix `c94c9345008cf6e339a9f90f59afccc18adea39f` removes SP trimming from the explicit locale path. The raw persisted/session value now reaches the RFC 5646 structural checks unchanged, so surrounding SP is rejected as malformed. The `Accept-Language` parser keeps its SP/HTAB handling because that is an HTTP field-value concern rather than a language-tag normalization rule.

## Rejected alternatives

### Keep the broad subtag regex because only the primary language is used

Rejected. Persisted/session preference is itself product data. A malformed suffix should not be accepted simply because the first subtag happens to map to a supported release locale.

### Reuse the `Accept-Language` language-range regex

Rejected. RFC 4647 basic language ranges deliberately have a broader structural grammar than RFC 5646 language tags. Sharing the same regex would preserve the original boundary confusion.

### Trim explicit locale strings before validation

Rejected. Trimming converts malformed persisted/session identity data into a different valid language tag and hides the rejecting boundary. HTTP OWS handling belongs only to the `Accept-Language` parser; RFC 5646 language-tag syntax itself does not permit whitespace.

### Validate every subtag against the live IANA Language Subtag Registry

Not selected for this slice. RFC 5646 defines well-formedness separately from registry validity. A registry-validity guarantee would require a pinned registry version, update/release process, reproducibility evidence, and failure policy; none belongs implicitly inside this bounded pure-domain repair.

### Treat private-use-only or grandfathered values as malformed because Naruon cannot render them

Rejected. Support is a product-release question after syntax classification. Collapsing well-formed unsupported values into `ui_locale_input_invalid` would make error semantics depend on the current release set and contradict the RFC 5646 syntax contract.

## Downstream contract

Persistence and future authoring/API boundaries must keep explicit locale values on this RFC 5646 well-formedness path and must not substitute the broader `Accept-Language` range grammar. They also must not trim or otherwise rewrite explicit locale identity before validation. A well-formed tag that lacks a supported release primary fails as unsupported; malformed syntax fails as input-invalid. Fixed regular/irregular grandfathered values must be recognized before ordinary structural guards rather than reinterpreted from apparent subtags. A pinned registry-validity requirement may be added later only as an explicit versioned contract.

## Traceability

- Seventeenth RED: `478bd95fdbd2b6601fae1ab70c3513abf0f985fe`.
- Seventeenth causal source fix: `3a87209306ad1b3dee67cb9e0e9e513dfb7a4f3a`.
- Eighteenth RED: `8d9a0f67a47b26eb1e36a7bc65681470033c6f74`.
- Eighteenth causal source fix: `aceef1b282d948411fe9b04b8cd08750fcdacfe8`.
- Nineteenth RED: `d23d4095d1c2ac8542f1ac247b6fee87fcb9485c`.
- Nineteenth causal source fix: `dc077bec9ae47e1421fa678ae43451f65784c410`.
- Twenty-fourth RED: `2ff28c208b8fd5a83bee3e179f4d66b31831be43`.
- Twenty-fourth causal source fix: `c94c9345008cf6e339a9f90f59afccc18adea39f`.
- Twenty-fifth pre-existing RED: predecessor exact `97279b9dfd8d47d3033007d36398ccf7aa9e6943`, focused `zh-min-nan` regression.
- Twenty-fifth causal source fix: `8666ef7bf2451f4e4ca8e93c69d24d5a9fb6436c`.
- Canonical product Gap: #1731.
- Product/technical Gap ledger owner: #1602.

## References

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47; RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

Phillips, A., & Davis, M. (2006). *Matching of language tags* (BCP 47; RFC 4647). RFC Editor. https://doi.org/10.17487/RFC4647
