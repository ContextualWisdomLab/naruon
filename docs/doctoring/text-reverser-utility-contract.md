# Text reverser utility contract

## Problem

Generated PR #1770 introduced a useful `text_reverser` intent together with weaker duplicate implementations of the canonical `hash_generator` and `json_formatter`. The duplicates must not fork #1718 ownership.

## Decision

The successor adopts #1718 as real commit ancestry and retains only `text_reverser`. The handler reuses `UTILITY_TEXT_MAX_CHARS` (100,000 characters), the registry parameter-validation contract, and the existing tool execution/error boundary. Reversal is explicitly defined as Python Unicode code-point order (`text[::-1]`); it is not advertised as grapheme-cluster transformation, cryptography, or identity/security functionality.

## Rejected alternatives

- Keeping #1770 hash/JSON implementations: rejected because they weaken the SHA-2-only/resource-limit/strict-JSON owner contract.
- Metadata-only retargeting: rejected because it does not create canonical ancestry.
- Unbounded input: rejected because utility handlers share the bounded resource contract.

## Traceability

Owner: #1718 `7fb5b9b2578f3a12ac757e1e1b9c5d490722bfd9`.
Generated finding: #1770.
Product code: `backend/api/tools.py::text_reverser_handler`.
Regression: `backend/tests/test_utility_tools_contract.py`.
