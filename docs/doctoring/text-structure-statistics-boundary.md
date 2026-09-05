# Text-structure statistics boundary

## Problem

The prepared `text_structure_statistics` service counted contiguous terminal-punctuation runs but exposed the result as `sentence_boundary_count`. That name overstates the implemented construct. A full stop can occur inside a decimal, hostname, abbreviation, or other non-sentence context, so punctuation-run counting is not sentence segmentation.

Unicode Standard Annex #29 makes the distinction explicit: default sentence boundaries are determined by a dedicated ordered ruleset, and the full stop is ambiguous across sentence endings, abbreviations, and numbers. The same annex also notes that reliable word segmentation for languages such as Chinese and Japanese requires dictionary lookup or other tailored mechanisms. A whitespace token count therefore cannot be presented as a locale-invariant word or readability measure.

The already product-visible `/api/tools/text_analyzer/execute` adapter had the same boundary problem in a different form: it returned `word_count = len(text.split())`, described that value to buyers as a word count, and computed `char_count_no_spaces` by removing only ASCII space, LF, CR, and TAB rather than all Unicode whitespace. Default-branch code search found those legacy keys only in `backend/api/tools.py` and its regression tests, with no additional repository consumer.

## Decision

Naruon keeps this capability descriptive and versioned rather than inferring an unsupported latent construct.

- `sentence_boundary_count` is removed before new service exposure.
- `terminal_punctuation_run_count` names exactly what the current regular expression measures.
- the segmentation contract advances from `whitespace-and-terminal-punctuation-v1` to `whitespace-and-terminal-punctuation-runs-v2` so downstream consumers cannot mistake the renamed field for the former sentence claim;
- whitespace-delimited tokens remain explicit descriptive counts only;
- periods inside decimals, hostnames, abbreviations, and similar text may contribute punctuation runs and are not reclassified as sentences;
- no readability score, language-independent word count, or sentence count is claimed.

For the existing `text_analyzer` API, an immediate hard deletion of `char_count`, `char_count_no_spaces`, and `word_count` would break an already exposed response contract. The adapter therefore delegates to `measure_text_structure`, exposes the truthful canonical fields, and retains the three old fields only as explicit compatibility aliases. The response includes a `legacy_aliases` mapping, and the catalog description states that `word_count` maps to `whitespace_token_count` rather than a linguistic word construct. `char_count_no_spaces` now aliases the Unicode-aware `non_whitespace_character_count`, removing the former ASCII-whitespace-only behavior.

A future contract-breaking release may remove those aliases after consumer migration evidence; until then they must not regain independent implementation or stronger semantics than their canonical fields.

If a future buyer workflow needs word or sentence segmentation rather than transparent counts, it must adopt an explicit Unicode/locale-tailored segmentation contract and add representative multilingual acceptance evidence instead of silently changing this service's semantics.

## Alternatives rejected

Keeping `sentence_boundary_count` while documenting caveats was rejected because the field name itself would remain a misleading product contract. Adding ad-hoc exceptions for decimals, URLs, and common abbreviations was rejected because that would still be an incomplete sentence segmenter and would create locale-specific heuristics without a declared profile. Reintroducing the earlier synthetic readability score was rejected because these counts do not establish a calibrated readability construct.

Silently deleting the three established `text_analyzer` response fields in this stacked feature PR was also rejected because it would turn a semantic correction into an undocumented API break. Keeping the old implementation untouched was rejected because it would leave buyer-visible `word_count` semantics and incomplete Unicode whitespace handling in place. Explicit aliases make the migration observable while centralizing the calculation in one service.

## Executable traceability

- Service RED: `fbc8dd378e50e9e16a2992d9f11ce1d7ccdaf0d1` changes the focused contract to require `terminal_punctuation_run_count`, contract version `v2`, absence of `sentence_boundary_count`, and an explicit decimal/URL punctuation example. Against the preceding implementation the exact focused harness reports 4 failures and 6 passes, all four failures caused by the missing renamed field.
- Service causal fix: `7e8559b83c08427f76098798edd683a1dd777ad6` renames the field and pattern, advances the contract version, and narrows the docstring claim without changing the underlying punctuation-run algorithm.
- Service focused exact-file harness on the fix reports 10 passed, 0 failed in 0.11 s.
- Adapter RED: `6b7396a4660e049b6ec4180167ef92b9a62c4416` adds the product-adapter contract for canonical descriptive fields, Unicode whitespace, compatibility aliases, and truthful catalog disclosure. An isolated exact-contract harness against the preceding adapter reports 2 failed, 0 passed: the canonical fields are absent and the catalog still says `단어 수`.
- Adapter causal fix: `fc331fa0665e0c1569c2fb40d6eee57bb3ee9397` delegates `text_analyzer_handler` to `measure_text_structure`, publishes canonical fields and the versioned segmentation contract, keeps legacy fields only as declared aliases, and removes the buyer-facing word-count claim. The isolated focused adapter harness reports 2 passed, 0 failed in 0.09 s.
- Production owners: `backend/services/text_structure_statistics.py` and `backend/api/tools.py`.
- Regression owners: `backend/tests/test_text_analysis_services.py` and `backend/tests/test_text_analyzer_measurement_contract.py`.

The isolated focused harnesses establish only the causal service/adapter slices. Repository dependency installation, existing `test_tools_api.py`, whole-suite coverage, hosted required checks, independent approval, protected merge, and release remain separate gates.

## Reference

Unicode Consortium. (2025). *Unicode text segmentation* (Unicode Standard Annex No. 29, Unicode 17.0.0, Revision 47). https://www.unicode.org/reports/tr29/
