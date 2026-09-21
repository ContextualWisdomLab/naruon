# UI localization: BCP 47 registry-independent validity guard

## Decision

Naruon's explicit-locale policy distinguishes three boundaries:

1. structural `Language-Tag` syntax accepted by RFC 5646 ABNF, including private-use-only and grandfathered forms;
2. registry-independent RFC 5646 validity constraints that can be checked without consulting a moving IANA Language Subtag Registry snapshot;
3. Naruon's release support set (`ko`, `en`, `ja`, `zh`, `vi`, `es`, `de`, `fr`).

The policy now rejects a structural `langtag` that repeats the same extension singleton before the private-use `x` boundary. RFC 5646 §2.2.6 requires each singleton subtag to appear at most once outside private use and gives `en-a-bbb-a-ccc` as an invalid example while allowing `en-a-bbb-x-a-ccc` because the second `a` is private-use data.

This is intentionally narrower than full BCP 47 validity. RFC 5646 validity also depends on a dated IANA Language Subtag Registry and prohibits duplicate variant subtags. This bounded policy does not claim live registry validation or canonicalization. A future owner may add registry-backed validity only with an explicit version/update contract and reproducible evidence.

## Finding

The existing `_LANGTAG_PATTERN` mirrors the structural ABNF closely enough that it accepted `en-a-bbb-a-ccc`: each `a` independently satisfied the extension-singleton production. That made an RFC-invalid tag appear to be a supported `en` locale.

The failure is product-significant even though Naruon ultimately collapses supported tags to their primary release language. Persisted/session locale input is an authority boundary; accepting a tag that violates a normative RFC invariant makes validation semantics depend on which downstream component revalidates the original tag.

## RED and causal repair

RED commit `da7e2653a158a259f4d327f1cf017674c7721064` adds an executable regression requiring repeated extension singleton tags to fail with `ui_locale_input_invalid`, while preserving `en-a-bbb-x-a-ccc -> en`.

Causal fix `81e061c000a13261ced87b7d6f71fbce64637821` adds a bounded structural check after the existing `langtag` regex match. It tracks one-character extension singletons case-insensitively, stops at private-use `x`, and rejects the first repeat. Private-use-only and grandfathered paths are unchanged, as are Naruon's release-support semantics and 128-character input ceiling.

Rejected alternatives:

- **Treat ABNF match as sufficient validity.** Rejected because RFC 5646 explicitly adds non-ABNF validity constraints.
- **Reject every repeated one-character token including private use.** Rejected because RFC 5646 explicitly permits the singleton-shaped token after `x` as private-use data.
- **Introduce live IANA registry validation in this repair.** Rejected because it creates a moving external authority and versioning/update problem outside this pure-policy slice.
- **Canonicalize or silently repair the tag.** Rejected because explicit preferences fail closed; mutation would hide invalid caller input.

## Acceptance and follow-up

The focused regression is necessary but not sufficient for merge. The unchanged exact head still requires repository full-suite/coverage/security execution and qualifying independent post-last-push review. Future persistence and HTTP owners must preserve the same typed error boundary without truncation or silent canonical repair.

Duplicate variant subtags are another RFC 5646 validity condition. They remain a separate review target because identifying variants without a registry snapshot requires a deliberately scoped parser contract rather than broadening this singleton fix by assumption.

## Traceability

- Product Gap: #1731
- Pure policy owner: #1740
- Source: `backend/services/ui_localization_policy.py`
- Focused regression: `backend/tests/test_ui_localization_bcp47_extension_singletons.py`
- RED: `da7e2653a158a259f4d327f1cf017674c7721064`
- Causal fix: `81e061c000a13261ced87b7d6f71fbce64637821`

## Reference

Phillips, A., & Davis, M. (2009). *Tags for identifying languages* (BCP 47, RFC 5646). RFC Editor. https://doi.org/10.17487/RFC5646
