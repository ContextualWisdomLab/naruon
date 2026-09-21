# UI localization: BCP 47 registry-independent validity guards

## Decision

Naruon's explicit-locale policy separates three boundaries:

1. structural `Language-Tag` syntax accepted by RFC 5646 ABNF, including private-use-only and grandfathered forms;
2. registry-independent RFC 5646 validity constraints that can be checked without consulting a moving IANA Language Subtag Registry snapshot;
3. Naruon's release support set (`ko`, `en`, `ja`, `zh`, `vi`, `es`, `de`, `fr`).

The structural `langtag` branch now enforces three registry-independent validity rules in addition to ABNF shape:

- an extension singleton may appear at most once before the private-use `x` boundary;
- a variant subtag may not repeat case-insensitively before extensions/private use;
- despite the compatibility ABNF reserving up to three extlang positions, only the first extlang position may be occupied.

Those structural guards apply only to ordinary `langtag` values. RFC 5646's fixed `grandfathered` alternatives are complete registered tags whose apparent subtags cannot be reinterpreted as extlang/variant structure. The fixed regular and irregular grandfathered lists are therefore recognized before registry-independent structural guards are applied.

These checks intentionally remain narrower than full BCP 47 validity. Registry membership, variant `Prefix` relationships, deprecation, preferred values, canonicalization, and other registry-dated semantics still require a versioned IANA Language Subtag Registry authority and are not inferred here.

## Findings

### Repeated extension singleton

The existing `_LANGTAG_PATTERN` accepted `en-a-bbb-a-ccc`: each `a` independently satisfied the extension-singleton production. RFC 5646 §2.2.6 requires each singleton subtag to appear at most once outside private use and explicitly makes that form invalid, while `en-a-bbb-x-a-ccc` remains valid because the second `a` is private-use data.

RED `da7e2653a158a259f4d327f1cf017674c7721064` pinned the failure. Causal fix `81e061c000a13261ced87b7d6f71fbce64637821` added the bounded case-insensitive singleton check and stopped evaluation at private-use `x`.

### Duplicate variant subtag

A structural ABNF match also accepted duplicate variants such as `en-1901-1901` and case variants such as `en-oxendict-OXENDICT`. RFC 5646 §2.2.9 states that a valid tag contains no duplicate variant subtags. This condition is registry-independent once the structural parser has identified the variant segment.

RED `c34b45957799575ea7e11c84992fdf84461b783f` requires both duplicate forms to fail with `ui_locale_input_invalid`, while preserving `en-1901-x-1901 -> en` because the second spelling is private-use data. Causal fix `96adc96dd5fab6e31734c2c23257b0f0f40447ee` walks the structural positions after primary/extlang/script/region, compares variant spellings case-insensitively, and stops before extensions/private use.

### Reserved second and third extlang positions

RFC 5646 §2.2.2 explains that the `extlang` ABNF retains up to three positions for compatibility, but the second and third positions are permanently reserved: tags occupying them are and will always remain invalid. The RFC 5646 errata record also notes that §2.2.9's compact validity list omitted this condition even though §2.2.2 makes it normative.

The previous regex therefore accepted `zh-cmn-yue` and normalized it to `zh`. RED `c49c80904ae1c38ee529a4b65e2fdb6612863c47` requires that form to fail with `ui_locale_input_invalid` while preserving the single-extlang form `zh-cmn-Hans-CN -> zh`. Causal fix `983194dd129cc593a4caa3c8531fb669986e4262` rejects structural tags that occupy more than one three-letter extlang position immediately after a two- or three-letter primary language subtag.

### Grandfathered tags are not ordinary structural subtags

Fresh code-current review of predecessor `97279b9dfd8d47d3033007d36398ccf7aa9e6943` found a contradiction between the fixed grandfathered-tag regression and production control flow. `backend/tests/test_ui_localization_bcp47_well_formedness.py` already requires `zh-min-nan -> zh`, but `_LANGTAG_PATTERN` also matches that spelling as `zh` plus two apparent three-letter extlang positions. The generic multi-extlang guard therefore rejected the RFC-defined grandfathered tag before the grandfathered alternative could be considered.

RFC 5646 §2.1 lists `zh-min-nan` in the fixed `regular` grandfathered production and explicitly states that regular grandfathered tags can appear to match `langtag` even though their apparent subtags do not carry the ordinary extlang/variant semantics. This is a fixed standards exception, not a moving IANA-registry lookup.

The realistic RED already existed on the predecessor exact head: the focused test expected `normalize_supported_locale("zh-min-nan") == "zh"`, while the source raised `ui_locale_input_invalid`. Causal fix `8666ef7bf2451f4e4ca8e93c69d24d5a9fb6436c` replaces the partial/misnamed grandfathered set with RFC 5646's complete fixed regular+irregular list and exempts exact grandfathered values from the ordinary structural duplicate/extlang guards. Unsupported grandfathered tags still fail at the product-support boundary as `ui_locale_unsupported`; no preferred-value rewriting or registry-date semantics are introduced.

## Product significance

Naruon ultimately collapses a supported explicit tag to one release language, but persisted/session locale input is still an authority boundary. Accepting an RFC-invalid tag here allows downstream systems to disagree about whether the original identity was admissible, while rejecting an RFC-defined grandfathered tag creates the opposite interoperability failure. The policy therefore recognizes the fixed RFC grandfathered alternatives first, applies stable registry-independent structural invariants only to ordinary `langtag` values, and then applies the eight-locale product-support check.

## Rejected alternatives

- **Treat ABNF match as sufficient validity.** Rejected because RFC 5646 explicitly adds validity rules outside the ABNF.
- **Treat regular grandfathered tags as ordinary extlang/variant sequences.** Rejected because RFC 5646 says their meaning is defined by the complete grandfathered registration even when they appear to match `langtag`.
- **Treat every repeated spelling after `x` as a duplicate.** Rejected because all subtags after the private-use singleton are private-use data.
- **Use live IANA lookup for this repair.** Rejected because the grandfathered alternatives are a fixed RFC list and a live registry would introduce a moving external authority without a version/update/reproducibility contract.
- **Canonicalize grandfathered tags to Preferred-Value.** Rejected because that is a registry/canonicalization policy outside this pure admission boundary and would rewrite caller identity.
- **Canonicalize or silently repair invalid caller input.** Rejected because explicit locale preferences are an authority boundary and fail closed.
- **Ban extlang entirely.** Rejected because RFC 5646 still permits one extlang position and Naruon's release-level normalization can preserve that structural compatibility without claiming registry canonicalization.

## Acceptance and follow-up

The focused regressions and causal source repairs are necessary but not sufficient for merge. The exact current head still requires repository full-suite/coverage/security execution and qualifying independent post-last-push review. Persistence and HTTP owners must preserve the typed invalid-versus-unsupported boundary without truncation, silent canonical repair, or reinterpretation of fixed grandfathered tags as ordinary subtag structure.

Full registry validity remains deliberately out of scope until an owner defines a dated IANA Language Subtag Registry version, update cadence, provenance, rollback behavior, and reproducible tests. Variant-prefix recommendations and canonical preferred-value replacement must not be guessed into this pure-policy slice.

## Traceability

- Product Gap: #1731
- Pure policy owner: #1740
- Source: `backend/services/ui_localization_policy.py`
- Focused regressions: `backend/tests/test_ui_localization_bcp47_extension_singletons.py`, `backend/tests/test_ui_localization_bcp47_well_formedness.py`
- Repeated-singleton RED/fix: `da7e2653a158a259f4d327f1cf017674c7721064` -> `81e061c000a13261ced87b7d6f71fbce64637821`
- Duplicate-variant RED/fix: `c34b45957799575ea7e11c84992fdf84461b783f` -> `96adc96dd5fab6e31734c2c23257b0f0f40447ee`
- Multi-extlang RED/fix: `c49c80904ae1c38ee529a4b65e2fdb6612863c47` -> `983194dd129cc593a4caa3c8531fb669986e4262`
- Grandfathered-structure RED: predecessor `97279b9dfd8d47d3033007d36398ccf7aa9e6943`, `test_explicit_locale_accepts_supported_primary_grandfathered_language_tags`
- Grandfathered-structure fix: `8666ef7bf2451f4e4ca8e93c69d24d5a9fb6436c`

## References

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47, RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

RFC Editor. (2018). *Errata ID 5457: RFC 5646, Section 2.2.9*. https://www.rfc-editor.org/errata/eid5457
