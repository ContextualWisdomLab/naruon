# UI localization RFC 4647 wildcard ordering repair

## Decision status

**Proposed.** This note extends the pure UI Localization Catalog policy owned by #1740 and does not create persistence, API, browser, Storybook, ontology-label, or LLM-translation ownership.

## Verified finding

The prior policy retained only supported concrete language ranges before applying RFC 4647 lookup wildcard ordering. That changed the meaning of a valid priority list such as:

```text
Accept-Language: *;q=0.9, pt-BR;q=0.8
```

RFC 4647 lookup says `*` is skipped when another language range follows in the language priority list. The later `pt-BR` range still exists even though Naruon's current release has no Portuguese resource. Lookup therefore tries the later concrete range, finds no supported resource, and reaches the product default. The prior implementation discarded `pt-BR` before deciding whether the wildcard had a later concrete range, so it incorrectly attributed the selected default to `accept_language` rather than `product_default`.

This is an authority/provenance defect, not a change to the selected locale value. `UiLocaleSelection.selection_source` is product state used to explain which authority tier selected the locale, so unsupported concrete ranges cannot be erased before wildcard lookup control flow is resolved.

## RED and causal repair

- RED `2ebe9758cb915841d86330bbabcd618f3f091d71` adds `*;q=0.9, pt-BR;q=0.8` and requires `(ko, product_default)`.
- Causal fix `1664d9707d4b5b9366b422f8faf612418ecd7789` records every positive-quality concrete range's priority before filtering against the eight supported product locales. Wildcard handling then skips the wildcard whenever any later positive concrete range remains in the RFC lookup priority order. Unsupported ranges still never become supported locale candidates.
- Existing positive wildcard behavior remains unchanged when the wildcard is the final effective range, and q=0 exclusions remain non-candidates.

The repair deliberately does not generalize Naruon into a full BCP 47 registry. Release resources remain exactly `ko/en/ja/zh/vi/es/de/fr`; the change preserves protocol ordering metadata long enough to compute the correct selection authority.

## Verification boundary

The source and focused regression are committed to the exact #1740 branch. This runtime cannot obtain an exact repository checkout, so no local/container PASS is claimed. Hosted checks and an independent post-last-push review must be reacquired on the final exact head; predecessor receipts do not transfer.

## TRACEABILITY

Phillips, A., & Davis, M. (2006). *Matching of language tags* (RFC 4647, BCP 47). RFC Editor. https://doi.org/10.17487/RFC4647

Fielding, R. T., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

RFC 4647 §3.4.1 specifies that in lookup the special range `*` is skipped when followed by other language ranges; if no later range matches, the default value is returned. RFC 9110 supplies the weighted `Accept-Language` language-priority list. Naruon preserves that ordering rule while reducing successful matches to its eight release locales.
