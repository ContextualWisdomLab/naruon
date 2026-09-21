# UI localization RFC 4647 wildcard ordering repair

## Decision status

**Proposed.** This note extends the pure UI Localization Catalog policy owned by #1740 and does not create persistence, API, browser, Storybook, ontology-label, or LLM-translation ownership.

## Verified findings

The first repair found that the policy retained only supported concrete language ranges before applying RFC 4647 lookup wildcard ordering. That changed the meaning of a valid priority list such as:

```text
Accept-Language: *;q=0.9, pt-BR;q=0.8
```

RFC 4647 lookup says `*` is skipped when another language range follows in the language priority list. The later `pt-BR` range still exists even though Naruon's current release has no Portuguese resource. Lookup therefore tries the later concrete range, finds no supported resource, and reaches the product default. The prior implementation discarded `pt-BR` before deciding whether the wildcard had a later concrete range, so it incorrectly attributed the selected default to `accept_language` rather than `product_default`.

A later standards recheck found the symmetric provenance defect when `*` is the only effective positive range. RFC 4647 §3.4 states that `*` does not convey enough information to choose a language tag: when it is the only range, or when no language range follows it, lookup computes the default value. The policy instead materialized the configured product default as an `accept_language` result, so `Accept-Language: *;q=0.9` selected the same locale value but reported the wrong authority tier. The defect also appeared with a non-Korean configured default.

These are authority/provenance defects, not necessarily selected-locale defects. `UiLocaleSelection.selection_source` is product state used to explain which authority tier selected the locale, so wildcard control flow and unsupported concrete ranges cannot be collapsed into a fabricated header-selected locale.

## RED and causal repairs

- RED `2ebe9758cb915841d86330bbabcd618f3f091d71` adds `*;q=0.9, pt-BR;q=0.8` and requires `(ko, product_default)`.
- Causal fix `1664d9707d4b5b9366b422f8faf612418ecd7789` records every positive-quality concrete range's priority before filtering against the eight supported product locales. Wildcard handling then skips the wildcard whenever a later positive concrete range remains in the RFC lookup priority order. Unsupported ranges still never become supported locale candidates.
- RED `deaf07941cfc2b607c2148f434ce1196a3db29d9` pins wildcard-only provenance for both the ordinary Korean default and a custom supported default: `*;q=0.9` must return `(ko, product_default)`, and the same input with `product_default="fr"` must return `(fr, product_default)`.
- Causal fix `1ce7b6ed5883beda305ea2552ae5af00509510c7` stops a wildcard from manufacturing an `accept_language` selection when no supported q=0 exclusion changes the fallback set. The caller therefore computes the configured product default and records `selection_source=product_default`. Existing supported q=0 exclusions remain meaningful: when the header explicitly excludes the configured default, wildcard fallback may still choose the first non-excluded release locale and truthfully remain header-dependent.

The repair deliberately does not generalize Naruon into a full BCP 47 registry. Release resources remain exactly `ko/en/ja/zh/vi/es/de/fr`; the change preserves protocol ordering and exclusion metadata long enough to compute the correct selection authority.

## Verification boundary

The source and focused regressions are committed to the exact #1740 branch. This runtime cannot obtain an exact repository checkout, so no local/container PASS is claimed. Hosted checks and an independent post-last-push review must be reacquired on the final exact head; predecessor receipts do not transfer.

## TRACEABILITY

Phillips, A., & Davis, M. (2006). *Matching of language tags* (RFC 4647, BCP 47). RFC Editor. https://doi.org/10.17487/RFC4647

Fielding, R. T., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

RFC 4647 §3.4 specifies that the special range `*` is skipped when later language ranges remain, and that when `*` is the only range or no range follows it, the default value is computed. RFC 4647 §3.4.1 requires the application to define that defaulting behavior. RFC 9110 supplies the weighted `Accept-Language` language-priority list. Naruon preserves those ordering and defaulting rules while reducing successful matches to its eight release locales.
