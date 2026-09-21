# UI Localization Catalog domain policy

## Decision status

This document records the executable pure-domain slice for issue #1731. It remains **Proposed** and deliberately stops before persistence, API delivery, browser caching, catalog publication, Storybook composition, or page migration.

The canonical workspace/Alembic owner is still #1503. Translation persistence must not create a migration from protected `develop` while that lineage is unintegrated. When #1503 or a verified complete successor reaches protected ancestry, the catalog persistence work must create the next ordinary descendant from the then-current single Alembic head.

Open work already contains unrelated `ADR-0005` proposals. This slice therefore does not allocate another ADR number before live ADR-owner reconciliation.

## Bounded context and ubiquitous language

The **UI Localization Catalog** bounded context owns UI-copy identity and locale selection only. Ontology/concept labels are a separate authority and must not be stored or served through the same resource.

Current domain objects are:

- `SupportedLocaleCode`: exactly `ko`, `en`, `ja`, `zh`, `vi`, `es`, `de`, `fr`;
- `UiLocaleSelection`: selected locale plus the authority tier that selected it;
- `screen_key`: dotted lowercase product-screen identity such as `settings.identity`;
- `message_key`: lowercase snake-case message identity within a screen;
- `placeholder_schema`: immutable named interpolation fields a published translation must preserve.

Locale authority is persisted preference → session preference → weighted `Accept-Language` → product default. Explicit persisted/session values are validated rather than silently replaced. Regional/script variants resolve to one release-level product language; this is intentionally narrower than a general-purpose BCP 47 registry.

## Locale and HTTP negotiation boundary

Stable machine-readable validation codes belong to the boundary that rejects the input.

Explicit locale input rejects every C0 control and DEL before normalization. Only ASCII SP is benign outer whitespace. `Accept-Language` applies HTTP field semantics instead: C0/DEL controls are rejected except HTAB where RFC 9110 permits it as OWS, and only SP/HTAB are normalized as optional whitespace. Python `str.strip()` and regex `\s` are intentionally not protocol authority.

The quality parameter name is case-insensitive, so `q=` and `Q=` carry identical parameter-name semantics while qvalue syntax remains strict.

`Accept-Language` is an HTTP list field. RFC 9110 §5.6.1.2 requires recipients to ignore a reasonable number of empty list elements while not tolerating enough to create a denial-of-service mechanism. Naruon therefore ignores at most 32 empty members and rejects the 33rd with `ui_accept_language_invalid`. Empty members never become wildcard/default votes.

RFC 4647 lookup ordering metadata is preserved even for release-unsupported ranges. For `*;q=0.9, pt-BR;q=0.8`, the later concrete range still exists in the language priority list, so the wildcard does not claim the selection. Portuguese then fails to match the eight release locales and the result reaches `product_default`.

The product default is also runtime-validated before set membership. Type annotations cannot prevent an arbitrary caller from supplying an unhashable object, so invalid defaults fail with `ui_locale_unsupported` rather than raw Python `TypeError`.

### Explicit parser resource limits

The policy now bounds valid as well as malformed negotiation input before expensive normalization/list work:

- explicit persisted/session locale value: at most **128 characters**;
- raw `Accept-Language` field value: at most **8192 characters**;
- non-empty `Accept-Language` members: at most **64**;
- ignored empty members: at most **32**.

These are Naruon product limits, not IETF constants. Over-limit values are rejected; they are never truncated. RFC 9110 §5.4 permits implementations to refuse field values larger than they are willing to process, while RFC 4647 §4.4 and RFC 5646 §4.4.1 permit documented language range/tag length limits. RFC 5646 requires limited-buffer protocols to support at least 35 characters; the 128-character explicit-locale budget exceeds that minimum. Outer proxies/HTTP servers may impose stricter limits and are not weakened by this policy.

The focused resource-bound record is `docs/doctoring/ui-localization-negotiation-resource-bounds.md`.

## Placeholder invariant

Translation publication preserves the exact named placeholder schema. Only simple lowercase named fields such as `{account_name}` are accepted. Attribute/index traversal, positional fields, conversion flags, format-specifier syntax, malformed braces, missing placeholders, and extra placeholders fail closed.

The schema container is itself part of the boundary. Runtime callers may provide only tuple/list collections. A mapping, generator, scalar, `None`, or arbitrary iterable is not silently coerced. Elements are validated as strings matching the placeholder-name grammar before duplicate detection so nested mutable values cannot leak raw hashability errors.

Python's `Formatter.parse()` normalizes an explicit empty format specifier: `{name}` and `{name:}` both expose an empty parsed `format_spec`. Because Naruon's catalog contract forbids format-specifier syntax entirely, the policy performs a narrow lexical check for real replacement fields containing `:` or `!` before `Formatter.parse()`, while doubled braces remain literals. See `docs/doctoring/ui-localization-placeholder-canonical-syntax.md`.

This is catalog integrity validation, not a rendering engine.

## Translation text persistence boundary

A Python `str` is not sufficient proof that catalog text can cross the UTF-8/PostgreSQL boundary. PostgreSQL character types cannot store U+0000, and Unicode scalar values exclude surrogate code points U+D800–U+DFFF. The policy therefore rejects NUL and isolated surrogate code points before placeholder parsing with `ui_translation_input_invalid`.

Ordinary Unicode text, combining marks, CJK text, newlines, and horizontal tabs remain valid. The policy does not rewrite user-facing copy.

## Rejected alternatives

A browser-wide catalog bundle and per-key network fetches are rejected in favor of future screen-scoped versioned resources. A new translation table/Alembic revision in this PR is rejected because it would create a parallel migration authority ahead of #1503. Locale parsing duplicated inside routes/components is rejected because it would fragment precedence and fallback semantics.

Generic runtime whitespace, case-sensitive `q`, unconditional rejection of recipient-side empty list members, unbounded empty-member tolerance, truncation of oversized locale/header values, and dependence on reverse-proxy/framework header limits are rejected. The pure policy is callable outside the future HTTP route, so its resource and syntax boundaries must be explicit and deterministic.

Coercing arbitrary placeholder iterables, running `set(schema)` before element validation, and deferring NUL/surrogate rejection to downstream drivers/codecs are rejected because they leak implementation-specific runtime failures instead of stable product errors.

LLM translation is outside this slice. Future assisted translation must use a released contextual-orchestrator contract and cannot bypass deterministic publication/completeness/placeholder validation.

## Verification and repair history

The focused policy suite covers supported-language identity, precedence, regional/script normalization, weighted `Accept-Language`, duplicate ranges, wildcard/q=0 handling, malformed/control input, screen/message identity, literal braces, placeholder schema mismatch/formatter features, runtime schema-container rejection, unhashable schema elements, translation-text persistence, product-default runtime typing, and explicit parser resource limits.

The branch now contains **fourteen ordinary-forward RED→repair sequences**. The first three established wildcard/q=0 basics, boundary-specific control codes, and control rejection before whitespace normalization. Subsequent repairs are:

4. RED `8265e9bb08cc407c860f148f1823dd0f4ab6d13d` → fix `9a6c8bb04be237c968b58987ca6ac4efb789a482`: replace generic Python whitespace semantics with boundary-specific SP/HTAB/C0 rules.
5. RED `962e250c54d0da324ec29b21283ab0b02cd55e8c` → fix `b20b5593498c09855e6ef6fb213d9bf6ea764e15`: case-insensitive `q`/`Q` parameter name.
6. RED `e299d29b14943c368e581bcb3d35303a1ba3fb8f` → fix `92a50acef8c7a3fbb38a926994add1641ac6c49d`: tuple/list-only placeholder schema container.
7. RED `3e251cc253d2ccf62ec1a3209ab629c6cffbe149` → fix `dec6c694dcf930ef184b158de04260d8db433bec`: reject NUL/surrogate/non-string translation input.
8. RED `489bfd4fa2d6f3630cf33412f6d910d73c47e110` → fix `244cff4f8d8805f2b3eacf91a75c7da84052bfc2`: validate schema elements before hash-based uniqueness.
9. RED `652137bd5b4fae436af207d8823a4e6e5122b8a0` → fix `f079bb270aadb2748937d5491b718e87b4198834`: runtime product-default type validation before set membership.
10. RED `20a7475c190585a1f94d34bd19c363f97dcc4e81` → fix `eff473a04fd8cca5d76396c36ff0c1dbf3a033f6`: RFC 9110 recipient-side empty-list semantics.
11. RED `7a68f034ef817abdad2c5744d8cbf4d0cf65ce03` → fix `b88aff67897bed9a533d21987d2db2618144b850`: bound ignored empty members at 32.
12. RED `2ebe9758cb915841d86330bbabcd618f3f091d71` → fix `1664d9707d4b5b9366b422f8faf612418ecd7789`: preserve later unsupported concrete ranges for truthful RFC 4647 wildcard control flow and `selection_source`.
13. RED `8b19c7dfe43e3dca3c1e4b8980c0a9998a3aec43` → fix `6ed310e1065940fa14c258b48412490e7b98d751`: distinguish canonical `{name}` from forbidden `{name:}` before parser normalization.
14. RED `978fdbbc6135fa88a8d43e0971ed075ae546f9de` → fix `0fdb5371eef63d6d7abe87ac14b69269c8519ff8`: bound explicit locale length, raw `Accept-Language` length, and non-empty member count before parser work.

Focused traceability for repair 14 is commit `d25c7a627af720242c9503f8f2b90553c7c94405`.

This automation environment does not contain an exact repository checkout, so no full-suite/local-container PASS is claimed for the current head. Exact-head hosted CI/security and qualifying independent post-last-push review must settle naturally. No source-neutral wake commit or predecessor receipt transfer is authorized.

## Next causal work

After canonical migration ancestry is protected, add versioned catalog aggregates and an ordinary Alembic descendant with immutable published-version semantics, item-level idempotent authoring, and tenant/workspace authorization. Then add a screen-scoped async read endpoint with version/ETag identity and realistic k6/E2E evidence, followed by page composition and KO/EN/JA/ZH/VI/ES/DE/FR Storybook/browser/a11y acceptance covering normal/loading/empty/error/permission states, CJK wrapping/font fallback, text expansion, keyboard/focus/touch, and assistive technology.

## TRACEABILITY

Fielding, R. T., Nottingham, M., & Reschke, J. (2022). *HTTP semantics* (RFC 9110). RFC Editor. https://doi.org/10.17487/RFC9110

Phillips, A., & Davis, M. (2006). *Matching of language tags* (RFC 4647, BCP 47). RFC Editor. https://doi.org/10.17487/RFC4647

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (RFC 5646, BCP 47). RFC Editor. https://doi.org/10.17487/RFC5646

Python Software Foundation. (2026). *string — Common string operations: Format string syntax* (Python 3.14 documentation). https://docs.python.org/3.14/library/string.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: Character types*. https://www.postgresql.org/docs/18/datatype-character.html

The Unicode Consortium. (2026). *The Unicode Standard, Version 18.0: Core specification, Chapter 3*. https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-3/

RFC 9110 defines `Accept-Language` as weighted language ranges, OWS as SP/HTAB, recipient-side list behavior, and implementation-specific field processing limits. RFC 4647 supplies lookup and range-length considerations. RFC 5646 supplies language-tag length guidance and explicitly permits documented refusal above an implementation limit rather than semantic-changing truncation. PostgreSQL/Unicode references define the persistence/scalar-value boundary. Python format-string documentation explains why canonical placeholder source requires a lexical check before parsed field semantics.
