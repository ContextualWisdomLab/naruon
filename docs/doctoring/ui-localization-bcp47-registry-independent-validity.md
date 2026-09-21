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

## Product significance

Naruon ultimately collapses a supported explicit tag to one release language, but persisted/session locale input is still an authority boundary. Accepting an RFC-invalid tag here allows downstream systems to disagree about whether the original identity was admissible, which weakens persistence, cache identity, auditability, and future API interoperability. The policy therefore fails closed on these stable registry-independent invariants before applying the eight-locale support check.

## Rejected alternatives

- **Treat ABNF match as sufficient validity.** Rejected because RFC 5646 explicitly adds validity rules outside the ABNF.
- **Treat every repeated spelling after `x` as a duplicate.** Rejected because all subtags after the private-use singleton are private-use data.
- **Use live IANA lookup for this repair.** Rejected because that would introduce a moving external authority without a registry version/update/reproducibility contract.
- **Canonicalize or silently repair invalid caller input.** Rejected because explicit locale preferences are an authority boundary and fail closed.
- **Ban extlang entirely.** Rejected because RFC 5646 still permits one extlang position and Naruon's release-level normalization can preserve that structural compatibility without claiming registry canonicalization.

## Acceptance and follow-up

The focused regressions and causal source repairs are necessary but not sufficient for merge. The exact current head still requires repository full-suite/coverage/security execution and qualifying independent post-last-push review. Persistence and HTTP owners must preserve the typed invalid-versus-unsupported boundary without truncation or silent canonical repair.

Full registry validity remains deliberately out of scope until an owner defines a dated IANA Language Subtag Registry version, update cadence, provenance, rollback behavior, and reproducible tests. Variant-prefix recommendations and canonical preferred-value replacement must not be guessed into this pure-policy slice.

## Traceability

- Product Gap: #1731
- Pure policy owner: #1740
- Source: `backend/services/ui_localization_policy.py`
- Focused regressions: `backend/tests/test_ui_localization_bcp47_extension_singletons.py`, `backend/tests/test_ui_localization_bcp47_well_formedness.py`
- Repeated-singleton RED/fix: `da7e2653a158a259f4d327f1cf017674c7721064` -> `81e061c000a13261ced87b7d6f71fbce64637821`
- Duplicate-variant RED/fix: `c34b45957799575ea7e11c84992fdf84461b783f` -> `96adc96dd5fab6e31734c2c23257b0f0f40447ee`
- Multi-extlang RED/fix: `c49c80904ae1c38ee529a4b65e2fdb6612863c47` -> `983194dd129cc593a4caa3c8531fb669986e4262`

## References

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47, RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646

RFC Editor. (2018). *Errata ID 5457: RFC 5646, Section 2.2.9*. https://www.rfc-editor.org/errata/eid5457
