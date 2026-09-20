# UI Localization Catalog domain policy

## Decision status

This document records the first executable domain slice for issue #1731. It is **Proposed** and deliberately stops before persistence, API delivery, browser caching, catalog publication, or page migration.

The canonical workspace/Alembic owner is still #1503. Translation persistence must not create a migration from protected `develop` while that lineage is unintegrated. When #1503 or a verified complete successor reaches protected ancestry, the catalog persistence work must create the next ordinary descendant from the then-current single Alembic head.

Open PRs already contain several unrelated `ADR-0005` proposals. This slice therefore does not allocate another ADR number before a complete live ADR-owner reconciliation. The absence of a new ADR number is intentional, not an implicit acceptance decision.

## Bounded context and ubiquitous language

The **UI Localization Catalog** bounded context owns UI-copy identity and selection only. Ontology/concept labels are a separate authority and must not be stored or served through the same resource.

Current domain objects are:

- `SupportedLocaleCode`: the release language identity, exactly `ko`, `en`, `ja`, `zh`, `vi`, `es`, `de`, `fr`;
- `UiLocaleSelection`: the selected locale plus the authority tier that selected it;
- `screen_key`: a dotted lowercase product-screen identity such as `settings.identity`;
- `message_key`: a lowercase snake-case message identity within a screen;
- `placeholder_schema`: the immutable set of named interpolation fields a published translation must preserve.

The locale authority order is persisted preference → session preference → `Accept-Language` → product default. Explicit persisted/session values are validated rather than silently replaced. `Accept-Language` quality values are bounded and malformed/control-character input fails closed. Regional/script variants resolve to one of the release-level product languages; this is intentionally narrower than preserving every BCP 47 variant as a separate catalog identity.

Stable machine-readable validation codes belong to the boundary that rejected the input. Explicit locale input rejects every C0 control and DEL before normalization and permits only ASCII SP as benign outer whitespace. `Accept-Language` applies the HTTP field-value boundary instead: C0/DEL controls are rejected except HTAB where RFC 9110 permits it as OWS, and only SP/HTAB are normalized as HTTP optional whitespace. Unicode whitespace, VT and FF are not treated as OWS. This distinction prevents Python's broader `str.strip()`/`\s` semantics from silently canonicalizing bytes that are outside the HTTP grammar, while preserving boundary-specific errors (`ui_locale_input_invalid` versus `ui_accept_language_invalid`).

## Placeholder invariant

Translation publication must preserve the exact named placeholder schema. The policy accepts only simple lowercase named fields such as `{account_name}`. Attribute/index traversal, positional fields, conversion flags, format specifications, malformed braces, missing placeholders, and extra placeholders fail closed with stable machine-readable error codes.

This is a catalog integrity boundary, not a rendering engine. It inspects placeholder syntax without evaluating it.

## Rejected alternatives

A browser-wide catalog bundle is rejected because the product contract calls for screen-scoped retrieval and version/cache identity. A per-key network fetch is also rejected because it turns normal rendering into repeated network chatter and creates inconsistent version visibility.

A new translation table or Alembic revision in this PR is rejected because it would create a parallel migration authority ahead of #1503. Locale parsing embedded independently in each route or component is rejected because it would produce inconsistent precedence and fallback rules.

Using Python `str.strip()` and regex `\s` as protocol whitespace is rejected. Python intentionally recognizes a broader Unicode whitespace set than HTTP OWS, while RFC 9110 defines OWS exactly as SP/HTAB. Protocol parsing therefore uses explicit ASCII whitespace sets rather than language-runtime whitespace classes.

LLM translation is outside this slice. Future assisted translation must use the released contextual-orchestrator contract and cannot bypass human/publication validation or placeholder integrity.

## Verification

The focused policy suite covers supported-language identity, precedence, regional/script normalization, weighted `Accept-Language`, duplicate ranges, wildcard handling, q=0 exclusion, malformed/control-character input, screen/message identity, literal braces, and placeholder schema mismatch/formatter features. The dedicated HTTP-whitespace regression covers VT/FF/Unicode-whitespace rejection, explicit-locale HTAB rejection, and valid SP/HTAB OWS around `Accept-Language` list members and q-weights.

The branch now contains four ordinary-forward RED→repair sequences. The first corrected wildcard lookup and q=0 fallback semantics. The second pinned boundary-specific validation codes for control characters. The third proved that CR/LF could disappear when `.strip()` ran before validation and moved control rejection ahead of normalization. The fourth RED `8265e9bb...` demonstrated that the remaining `.strip()` and regex `\s` semantics still accepted VT/FF, explicit-locale HTAB, and edge Unicode whitespace that are not part of the intended boundary; causal fix `9a6c8bb0...` rejects C0/DEL at the locale boundary, permits only HTTP HTAB where appropriate, restricts protocol OWS to `[ SP / HTAB ]`, and replaces generic stripping with explicit ASCII normalization.

No local/container PASS is claimed for the fourth repair because this automation environment cannot execute the repository test stack. The exact source and regression are committed, but current-head full-suite/coverage/hosted evidence and independent post-last-push review must be reacquired naturally. No source-neutral wake commit or predecessor receipt transfer is authorized.

## Next causal work

After the canonical migration ancestry is protected, add versioned catalog aggregates and an ordinary Alembic descendant with immutable published-version semantics, item-level idempotent UPSERT/authoring behavior, and tenant/workspace authorization where applicable. Only then add a screen-scoped read endpoint with version/ETag cache identity and page composition. UI acceptance must cover normal/loading/empty/error/permission states and KO/EN/JA/ZH/VI/ES/DE/FR text expansion, CJK wrapping/font fallback, keyboard/focus/touch and assistive technology before the UI Delivery Gate can pass.

## TRACEABILITY

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (RFC 5646, BCP 47). RFC Editor. https://doi.org/10.17487/RFC5646

Phillips, A., & Davis, M. (2006). *Matching of language tags* (RFC 4647, BCP 47). RFC Editor. https://doi.org/10.17487/RFC4647

Fielding, R. T., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

RFC 9110 defines `Accept-Language` as weighted language ranges, defines `weight = OWS ";" OWS "q=" qvalue`, and defines OWS exactly as zero or more SP/HTAB octets. It also states that field values containing CTL characters are invalid, with CR/LF/NUL specifically dangerous. RFC 4647 supplies language-range matching and RFC 5646 supplies language-tag structure. Naruon's first release intentionally reduces supported variants to eight product-language identities, so this module is a bounded product policy over those standards rather than a general-purpose BCP 47 library.
