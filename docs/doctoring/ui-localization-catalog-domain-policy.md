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
- `placeholder_schema`: the immutable ordered collection of named interpolation fields a published translation must preserve.

The locale authority order is persisted preference → session preference → `Accept-Language` → product default. Explicit persisted/session values are validated rather than silently replaced. `Accept-Language` quality values are bounded and malformed/control-character input fails closed. Regional/script variants resolve to one of the release-level product languages; this is intentionally narrower than preserving every BCP 47 variant as a separate catalog identity.

Stable machine-readable validation codes belong to the boundary that rejected the input. Explicit locale input rejects every C0 control and DEL before normalization and permits only ASCII SP as benign outer whitespace. `Accept-Language` applies the HTTP field-value boundary instead: C0/DEL controls are rejected except HTAB where RFC 9110 permits it as OWS, and only SP/HTAB are normalized as HTTP optional whitespace. Unicode whitespace, VT and FF are not treated as OWS. This distinction prevents Python's broader `str.strip()`/`\s` semantics from silently canonicalizing bytes that are outside the HTTP grammar, while preserving boundary-specific errors (`ui_locale_input_invalid` versus `ui_accept_language_invalid`).

The HTTP quality parameter name is case-insensitive. `q=` and `Q=` therefore carry identical weight semantics; rejecting `Q=` would incorrectly turn a valid `Accept-Language` field value into `ui_accept_language_invalid`. The policy keeps the value grammar strict while matching the parameter name case-insensitively.

## Placeholder invariant

Translation publication must preserve the exact named placeholder schema. The policy accepts only simple lowercase named fields such as `{account_name}`. Attribute/index traversal, positional fields, conversion flags, format specifications, malformed braces, missing placeholders, and extra placeholders fail closed with stable machine-readable error codes.

The schema container itself is part of the boundary. Runtime callers may provide only the declared tuple/list collection. A mapping, generator, scalar, `None`, or other iterable is not silently coerced into a schema. Each collection element is validated as a string matching the placeholder-name grammar before duplicate detection. This ordering matters: nested mutable values such as lists or mappings are unhashable, so applying `set(schema)` first would leak a raw Python `TypeError` instead of the stable `ui_placeholder_schema_invalid` contract. Container shape, element type/syntax, and uniqueness are therefore checked in that order.

This is a catalog integrity boundary, not a rendering engine. It inspects placeholder syntax without evaluating it.

## Translation text persistence boundary

A Python `str` is not by itself proof that catalog text is suitable for the product's UTF-8/PostgreSQL persistence path. PostgreSQL character types cannot store U+0000, and Unicode encoding forms operate on Unicode scalar values, which exclude surrogate code points U+D800–U+DFFF. The pure policy therefore rejects NUL and surrogate code points before placeholder parsing with the stable boundary code `ui_translation_input_invalid`.

The rule is intentionally narrow. Ordinary Unicode text, combining marks, CJK text, newlines and horizontal tabs remain valid translation content. This is not a generic control-character scrubber and does not rewrite user-facing copy; it prevents persistence/encoding failures from escaping later as database or codec exceptions.

## Rejected alternatives

A browser-wide catalog bundle is rejected because the product contract calls for screen-scoped retrieval and version/cache identity. A per-key network fetch is also rejected because it turns normal rendering into repeated network chatter and creates inconsistent version visibility.

A new translation table or Alembic revision in this PR is rejected because it would create a parallel migration authority ahead of #1503. Locale parsing embedded independently in each route or component is rejected because it would produce inconsistent precedence and fallback rules.

Using Python `str.strip()` and regex `\s` as protocol whitespace is rejected. Python intentionally recognizes a broader Unicode whitespace set than HTTP OWS, while RFC 9110 defines OWS exactly as SP/HTAB. Protocol parsing therefore uses explicit ASCII whitespace sets rather than language-runtime whitespace classes.

Treating the literal spelling `q` as case-sensitive is also rejected. RFC 9110 defines the content-negotiation weight parameter name `q` as case-insensitive; only its qvalue grammar remains strict.

Coercing an arbitrary iterable with `tuple(placeholder_schema)` is rejected. A one-key mapping can otherwise be accepted accidentally because iteration yields keys, while `None` raises a raw runtime exception before the localization policy can emit its stable boundary code.

Running duplicate detection with `set(schema)` before element validation is also rejected. An unhashable nested list or mapping would otherwise escape as a raw `TypeError`; the domain boundary must reject the element itself before any hash-based uniqueness operation.

Deferring NUL/surrogate rejection to PostgreSQL, JSON serialization, or an implicit UTF-8 encode is rejected. That would make publication correctness depend on whichever downstream sink is reached first and would replace a stable product error with driver/codec-specific failures.

LLM translation is outside this slice. Future assisted translation must use the released contextual-orchestrator contract and cannot bypass human/publication validation or placeholder integrity.

## Verification

The focused policy suite covers supported-language identity, precedence, regional/script normalization, weighted `Accept-Language`, duplicate ranges, wildcard handling, q=0 exclusion, malformed/control-character input, screen/message identity, literal braces, placeholder schema mismatch/formatter features, runtime schema-container rejection, and unhashable schema-element rejection. The dedicated HTTP-boundary regression covers VT/FF/Unicode-whitespace rejection, explicit-locale HTAB rejection, valid SP/HTAB OWS around `Accept-Language` list members and q-weights, and case-insensitive `q` parameter names. The dedicated translation-text regression covers leading/trailing NUL, high/low surrogate code points, non-string translation input, and a valid multiline Korean message so the repair does not collapse legitimate copy.

The branch now contains eight ordinary-forward RED→repair sequences. The first corrected wildcard lookup and q=0 fallback semantics. The second pinned boundary-specific validation codes for control characters. The third proved that CR/LF could disappear when `.strip()` ran before validation and moved control rejection ahead of normalization. The fourth RED `8265e9bb...` demonstrated that the remaining `.strip()` and regex `\s` semantics still accepted VT/FF, explicit-locale HTAB, and edge Unicode whitespace that are not part of the intended boundary; causal fix `9a6c8bb0...` rejects C0/DEL at the locale boundary, permits only HTTP HTAB where appropriate, restricts protocol OWS to `[ SP / HTAB ]`, and replaces generic stripping with explicit ASCII normalization. The fifth RED `962e250c54d0da324ec29b21283ab0b02cd55e8c` pins RFC 9110's case-insensitive quality-parameter name with `Q=` examples; causal fix `b20b5593498c09855e6ef6fb213d9bf6ea764e15` changes only the parameter-name matcher from literal `q` to `[qQ]`, preserving the existing qvalue and OWS grammar. The sixth RED `e299d29b14943c368e581bcb3d35303a1ba3fb8f` proves that `None` escapes as raw `TypeError` and a one-key mapping is silently accepted when the implementation blindly applies `tuple(...)`; causal fix `92a50acef8c7a3fbb38a926994add1641ac6c49d` validates the tuple/list container before conversion and preserves `ui_placeholder_schema_invalid` for invalid containers. The seventh RED `3e251cc253d2ccf62ec1a3209ab629c6cffbe149` proves that NUL, isolated surrogate code points, and non-string translation values are not rejected at the translation boundary; causal fix `dec6c694dcf930ef184b158de04260d8db433bec` adds `ui_translation_input_invalid` and validates persistable Unicode scalar text before `Formatter` parsing. The eighth RED `489bfd4fa2d6f3630cf33412f6d910d73c47e110` proves that a tuple/list containing an unhashable nested list or mapping reaches `set(schema)` and escapes as raw `TypeError`; causal fix `244cff4f8d8805f2b3eacf91a75c7da84052bfc2` validates every element as a valid string name before duplicate detection.

No local/container PASS is claimed for the fourth through eighth repairs because this automation environment does not contain the repository checkout needed for exact-head execution. The exact source and regressions are committed, but current-head full-suite/coverage/hosted evidence and independent post-last-push review must be reacquired naturally. No source-neutral wake commit or predecessor receipt transfer is authorized.

## Next causal work

After the canonical migration ancestry is protected, add versioned catalog aggregates and an ordinary Alembic descendant with immutable published-version semantics, item-level idempotent UPSERT/authoring behavior, and tenant/workspace authorization where applicable. Only then add a screen-scoped read endpoint with version/ETag cache identity and page composition. UI acceptance must cover normal/loading/empty/error/permission states and KO/EN/JA/ZH/VI/ES/DE/FR text expansion, CJK wrapping/font fallback, keyboard/focus/touch and assistive technology before the UI Delivery Gate can pass.

## TRACEABILITY

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (RFC 5646, BCP 47). RFC Editor. https://doi.org/10.17487/RFC5646

Phillips, A., & Davis, M. (2006). *Matching of language tags* (RFC 4647, BCP 47). RFC Editor. https://doi.org/10.17487/RFC4647

Fielding, R. T., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: Character types*. https://www.postgresql.org/docs/18/datatype-character.html

The Unicode Consortium. (2026). *The Unicode Standard, Version 18.0: Core specification, Chapter 3*. https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-3/

RFC 9110 defines `Accept-Language` as weighted language ranges, defines `weight = OWS ";" OWS "q=" qvalue`, defines OWS exactly as zero or more SP/HTAB octets, and explicitly states that the `q` parameter name is case-insensitive. It also states that field values containing CTL characters are invalid, with CR/LF/NUL specifically dangerous. RFC 4647 supplies language-range matching and RFC 5646 supplies language-tag structure. Naruon's first release intentionally reduces supported variants to eight product-language identities, so this module is a bounded product policy over those standards rather than a general-purpose BCP 47 library.

PostgreSQL 18 documents that character zero cannot be stored in character types. Unicode 18 defines Unicode scalar values as all Unicode code points except the high- and low-surrogate ranges and defines the Unicode encoding forms over scalar values. The seventh repair binds those external persistence/encoding constraints to the product's typed translation-input boundary without banning legitimate multiline or tabbed UI copy.

The placeholder-container and element-order repairs are internal product invariants rather than new standards interpretations: public/runtime boundaries must preserve stable localization validation codes and must not rely on incidental Python iteration or hashability behavior to define a versioned schema.
