# Email threading: References precedence

## Status and scope

This note documents the bounded production change in PR #1366. It is implementation evidence for the active PR, not shipped `develop` truth until that PR is integrated.

Naruon's deterministic thread assignment now treats a valid `References` chain as the ancestry source for lookup and fallback. `In-Reply-To` remains the fallback only when `References` contains no usable Message-ID. The change intentionally preserves Naruon's existing handling of multiple `In-Reply-To` IDs when the `References` fallback lane is active; a stricter RFC 5256 first-parent-only interpretation is outside this slice.

## Why the change is required

RFC 5322 defines `In-Reply-To` as identifying the message or messages to which a new message replies and `References` as identifying the conversation thread. RFC 5256's REFERENCES threading algorithm is more operationally specific: when `References` contains valid Message-IDs, those IDs are used to reconstruct ancestry; `In-Reply-To` is consulted only when `References` is absent or has no valid Message-ID.

The previous implementation combined both header sources and searched `In-Reply-To` first. If a valid `References` root and a conflicting `In-Reply-To` parent mapped to different already-imported threads, the result depended on the conflicting parent rather than the ancestry chain. If the referenced root had not yet arrived but the conflicting parent had, import order could also change the selected thread. Both cases are covered by RED-first regression tests in `backend/tests/test_threading_reference_precedence.py`.

## Product and safety effect

The fix reduces false conversation merges without adding subject heuristics, provider-specific trust, network access, model judgment, cross-tenant lookup, or a migration. Existing owner and organization filters remain the authorization boundary for ancestor lookup. Messages with no valid `References` retain the current `In-Reply-To` behavior, and messages with neither header retain Message-ID/UUID fallback behavior.

## Verification contract

The PR must demonstrate the focused regressions and the existing threading suite together, followed by the repository's exact-head backend, coverage, security, dependency, supply-chain, and independent-review gates. Predecessor-head or status-only evidence is not merge evidence.

## References

Crispin, M., & Murchison, K. (2008). *Internet Message Access Protocol - SORT and THREAD Extensions* (RFC 5256). RFC Editor. https://doi.org/10.17487/RFC5256

Resnick, P. W. (2008). *Internet message format* (RFC 5322). RFC Editor. https://doi.org/10.17487/RFC5322
