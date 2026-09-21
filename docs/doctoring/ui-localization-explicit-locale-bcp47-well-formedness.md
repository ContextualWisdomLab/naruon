# UI localization explicit-locale BCP 47 well-formedness

Status: Proposed with PR #1740. This record covers the pure explicit-locale policy only; it does not change the broader RFC 4647 `Accept-Language` language-range grammar.

## Problem

`normalize_supported_locale()` previously used the broad pattern `[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*`. That shape was adequate to recover a primary language but was not the RFC 5646 `Language-Tag` grammar. It accepted malformed explicit preferences such as `en-x` and `en-u`: both have a supported primary language, but RFC 5646 requires private-use `x` to be followed by at least one private-use subtag and an extension singleton such as `u` to be followed by at least one 2-8 character extension subtag.

Accepting those values as persisted/session locale identities made the explicit preference boundary weaker than its own documentation and blurred two different standards surfaces: RFC 5646 language tags for explicit stored/session identities versus RFC 4647 basic language ranges used inside `Accept-Language`.

A second standards sweep found the first structural repair incomplete. RFC 5646 defines `Language-Tag = langtag / privateuse / grandfathered`; some grandfathered values are intentionally outside the `langtag` production. For the current release-primary set, `en-GB-oed`, `zh-min`, and `zh-min-nan` therefore require explicit structural acceptance before release-level normalization. `zh-guoyu`, `zh-hakka`, and `zh-xiang` are grandfathered registry entries too, but their literal forms already satisfy the structural `langtag` pattern and do not need a separate alternation.

## RED

Commit `478bd95fdbd2b6601fae1ab70c3513abf0f985fe` adds focused cases that fail on the predecessor policy:

- `en-x` must fail with `ui_locale_input_invalid`;
- `en-u` must fail with `ui_locale_input_invalid`;
- `en-x-private` remains accepted and normalizes to `en`;
- `en-u-ca-gregory` remains accepted and normalizes to `en`.

Commit `8d9a0f67a47b26eb1e36a7bc65681470033c6f74` adds the follow-up grandfathered-tag regression:

- `en-GB-oed` normalizes to `en`;
- `zh-min` normalizes to `zh`;
- `zh-min-nan` normalizes to `zh`.

The regressions are intentionally scoped to explicit locale values. They do not tighten RFC 4647 language-range parsing in `Accept-Language`, where the grammar is different.

## Decision

Causal fix `3a87209306ad1b3dee67cb9e0e9e513dfb7a4f3a` replaces the permissive explicit-locale pattern with an RFC 5646 structural `langtag` pattern covering language/extlang, optional script and region, variants, extensions, and optional private-use suffix.

Follow-up causal fix `aceef1b282d948411fe9b04b8cd08750fcdacfe8` completes the supported-primary grandfathered-tag path by explicitly accepting `zh-min` and `zh-min-nan` alongside the already explicit `en-GB-oed`. This is a finite product-owned syntax compatibility set, not a live registry lookup. Grandfathered forms that already satisfy the structural `langtag` pattern need no separate exception.

The product continues to normalize a well-formed supported tag to its release-level primary language (`ko/en/ja/zh/vi/es/de/fr`). This is a syntax/well-formedness gate, not an IANA registry snapshot validator. RFC 5646 distinguishes well-formed tags from registry-valid tags; requiring a moving registry snapshot would create a separate versioned dependency that this pure policy does not currently own.

## Rejected alternatives

### Keep the broad subtag regex because only the primary language is used

Rejected. Persisted/session preference is itself product data. A malformed suffix should not be accepted simply because the first subtag happens to map to a supported release locale.

### Reuse the `Accept-Language` language-range regex

Rejected. RFC 4647 basic language ranges deliberately have a broader structural grammar than RFC 5646 language tags. Sharing the same regex would preserve the original boundary confusion.

### Validate every subtag against the live IANA Language Subtag Registry

Not selected for this slice. RFC 5646 defines well-formedness separately from registry validity. A registry-validity guarantee would require a pinned registry version, update/release process, reproducibility evidence, and failure policy; none belongs implicitly inside this bounded pure-domain repair.

### Treat grandfathered values as malformed because they do not fit `langtag`

Rejected. RFC 5646 defines grandfathered forms as part of `Language-Tag`. Rejecting `zh-min` or `zh-min-nan` merely because they sit outside the `langtag` branch would make the explicit-locale boundary contradict the standard it claims to implement.

## Downstream contract

Persistence and future authoring/API boundaries must keep explicit locale values on this RFC 5646 well-formedness path and must not substitute the broader `Accept-Language` range grammar. They may add a pinned registry-validity requirement later only as an explicit versioned contract.

## Traceability

- Seventeenth RED: `478bd95fdbd2b6601fae1ab70c3513abf0f985fe`.
- Seventeenth causal source fix: `3a87209306ad1b3dee67cb9e0e9e513dfb7a4f3a`.
- Eighteenth RED: `8d9a0f67a47b26eb1e36a7bc65681470033c6f74`.
- Eighteenth causal source fix: `aceef1b282d948411fe9b04b8cd08750fcdacfe8`.
- Canonical product Gap: #1731.
- Product/technical Gap ledger owner: #1602.

## References

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47; RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

Phillips, A., & Davis, M. (2006). *Matching of language tags* (BCP 47; RFC 4647). RFC Editor. https://doi.org/10.17487/RFC4647
