# UI Localization Catalog: canonical placeholder syntax

## Decision status

**Proposed.** This note records the thirteenth ordinary-forward repair in #1740. It changes only the pure placeholder-policy boundary; persistence, API delivery, browser rendering, catalog publication and authoring remain outside this PR.

## Finding

The catalog contract already says that published placeholders are simple named fields such as `{account_name}` and that conversion flags and format specifications are forbidden. The implementation used `string.Formatter.parse()` and rejected a field when `format_spec` was truthy or `conversion` was non-null.

That was insufficient for the source form `{account_name:}`. Python's format-string grammar treats the colon as the delimiter that introduces a `format_spec`, but an empty format specification has the same formatting result as the default. `Formatter.parse()` therefore yields an empty `format_spec` for both `{account_name}` and `{account_name:}`. The previous policy lost the lexical distinction and silently accepted a non-canonical spelling that its own contract said was forbidden.

This matters even though both forms render the same value. Catalog source is versioned publication data. If alternate lexical spellings are accepted as equivalent after parsing, source identity and validation semantics depend on lossy runtime normalization instead of the product contract.

## Decision

The policy now validates the replacement-field source before `Formatter.parse()` normalizes it. Escaped literal braces remain literals. For a real replacement field, the presence of `:` or `!` is rejected with `ui_placeholder_schema_invalid` before the parsed field-name/schema comparison runs.

The canonical accepted form remains exactly a simple named field such as `{account_name}`. `{account_name:}`, `{count:03d}`, `{account_name!r}`, attribute/index traversal and malformed fields are not alternate spellings of the schema; they are invalid publication input.

RED `8b19c7dfe43e3dca3c1e4b8980c0a9998a3aec43` adds the empty-format-specifier regression. Causal fix `6ed310e1065940fa14c258b48412490e7b98d751` preserves lexical operator information before the standard-library parser erases the empty-spec distinction.

## Rejected alternatives

Treating `{name:}` as equivalent to `{name}` is rejected because the product boundary explicitly forbids format-specifier syntax and published source identity should not depend on an implementation detail of `Formatter.parse()`.

Replacing the full parser with a bespoke interpolation engine is also rejected. Python's parser remains the authority for brace balancing and field decomposition; the product adds only the narrow lexical check required to preserve the stricter catalog grammar.

## Verification

The canonical policy suite now requires `{account_name:}` to fail with `ui_placeholder_schema_invalid`, alongside existing rejection of non-empty format specifications and conversions. Existing escaped-literal behavior remains owned by the same suite.

No local/container PASS or predecessor hosted receipt is claimed in this runtime. Current-head full-suite, coverage, security and independent review evidence must be reacquired on the exact post-repair head.

## TRACEABILITY

Python Software Foundation. (2026). *string — Common string operations: Format string syntax* (Python 3.14 documentation). https://docs.python.org/3.14/library/string.html

Python 3.14 defines a replacement field as a `field_name` optionally followed by `! conversion` and/or `: format_spec`, and documents that an empty format specification produces the same result as the default formatting behavior. `Formatter.parse()` returns the parsed `format_spec` value rather than preserving whether an empty `:` delimiter was present in the original source. Naruon therefore retains a stricter, source-aware catalog grammar on top of the standard parser rather than equating semantically similar but lexically different publication inputs.
