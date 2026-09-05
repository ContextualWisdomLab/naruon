# Text-structure statistics boundary

## Problem

The prepared `text_structure_statistics` service counted contiguous terminal-punctuation runs but exposed the result as `sentence_boundary_count`. That name overstates the implemented construct. A full stop can occur inside a decimal, hostname, abbreviation, or other non-sentence context, so punctuation-run counting is not sentence segmentation.

Unicode Standard Annex #29 makes the distinction explicit: default sentence boundaries are determined by a dedicated ordered ruleset, and the full stop is ambiguous across sentence endings, abbreviations, and numbers. The same annex also notes that reliable word segmentation for languages such as Chinese and Japanese requires dictionary lookup or other tailored mechanisms. A whitespace token count therefore cannot be presented as a locale-invariant word or readability measure.

## Decision

Naruon keeps this service descriptive and versioned rather than inferring an unsupported latent construct.

- `sentence_boundary_count` is removed before product-adapter exposure.
- `terminal_punctuation_run_count` names exactly what the current regular expression measures.
- the segmentation contract advances from `whitespace-and-terminal-punctuation-v1` to `whitespace-and-terminal-punctuation-runs-v2` so downstream consumers cannot mistake the renamed field for the former sentence claim;
- whitespace-delimited tokens remain explicit descriptive counts only;
- periods inside decimals, hostnames, abbreviations, and similar text may contribute punctuation runs and are not reclassified as sentences;
- no readability score, language-independent word count, or sentence count is claimed.

If a future buyer workflow needs word or sentence segmentation rather than transparent counts, it must adopt an explicit Unicode/locale-tailored segmentation contract and add representative multilingual acceptance evidence instead of silently changing this service's semantics.

## Alternatives rejected

Keeping `sentence_boundary_count` while documenting caveats was rejected because the field name itself would remain a misleading product contract. Adding ad-hoc exceptions for decimals, URLs, and common abbreviations was rejected because that would still be an incomplete sentence segmenter and would create locale-specific heuristics without a declared profile. Reintroducing the earlier synthetic readability score was rejected because these counts do not establish a calibrated readability construct.

## Executable traceability

- RED: `fbc8dd378e50e9e16a2992d9f11ce1d7ccdaf0d1` changes the focused contract to require `terminal_punctuation_run_count`, contract version `v2`, absence of `sentence_boundary_count`, and an explicit decimal/URL punctuation example. Against the preceding implementation the exact focused harness reports 4 failures and 6 passes, all four failures caused by the missing renamed field.
- Causal fix: `7e8559b83c08427f76098798edd683a1dd777ad6` renames the field and pattern, advances the contract version, and narrows the docstring claim without changing the underlying punctuation-run algorithm.
- Focused exact-file harness on the fix reports 10 passed, 0 failed in 0.11 s.
- Production owner: `backend/services/text_structure_statistics.py`.
- Regression owner: `backend/tests/test_text_analysis_services.py`.

The isolated focused harness establishes only this stdlib service/test slice. Repository dependency installation, whole-suite coverage, hosted required checks, independent approval, protected merge, and release remain separate gates.

## Reference

Unicode Consortium. (2025). *Unicode text segmentation* (Unicode Standard Annex No. 29, Unicode 17.0.0, Revision 47). https://www.unicode.org/reports/tr29/
