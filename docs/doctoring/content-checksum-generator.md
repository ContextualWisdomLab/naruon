# Content checksum generator — standards and product boundary

**Status:** active PR candidate; not shipped until merged through protected `develop`.

**Traceability:** bounded checksum slice of issue #1247, *Build an auditable data-hygiene utility suite*.

## Product contract

Naruon's `content_checksum_generator` compares the exact UTF-8 byte sequence supplied by the caller. It deliberately does **not** Unicode-normalize input before hashing, because normalization would change the byte-level evidence being compared. The deterministic tool accepts at most 1,048,576 UTF-8 bytes per invocation and exposes only these normal-surface algorithms:

- canonical `sha256`, with documented display spelling `SHA-256`;
- canonical `sha3_256`, with documented display spellings `SHA3-256` and `SHA-3-256`;
- canonical `blake2b_256`, with documented display spelling `BLAKE2b-256`.

Input matching for these canonical/display spellings is case-insensitive, and output always returns the canonical code. The mapping is an explicit presentation compatibility boundary, not free-form `hashlib` alias resolution. SHA-512, generic BLAKE2b, MD5, SHA-1 and other unlisted names remain outside the normal surface.

MD5 and SHA-1 are intentionally absent from the normal surface. NIST states that SHA-1 is being transitioned out for applying cryptographic protection by December 31, 2030; Naruon therefore does not introduce SHA-1 as a new customer-facing checksum choice. No legacy-compatibility checksum mode is part of this slice.

A returned digest is an equality/integrity fingerprint for the exact supplied bytes. It does not authenticate a sender, prove provenance, or replace a keyed MAC or digital signature. Customer-facing output carries that warning with every result so the next action is explicit: compare the digest with an independently obtained expected digest when checking content equality; use an authenticated construction when sender or origin authenticity matters.

## Catalog/API label mismatch finding and repair

Generated hash-tool provenance PR #1739 carried a review finding that human-facing algorithm names could be rejected by the execution boundary. Fresh inspection confirmed the same narrower mismatch on the canonical checksum owner: the catalog description advertised `SHA-256`, `SHA-3-256`, and `BLAKE2b-256`, while the handler accepted only internal codes.

The repair is deliberately bounded. Regression `d23b6f82d61de219ceb6fc0eec7781d810a580f4` requires documented display labels to resolve to canonical codes. Production fix `e1a0d464fcfcecca7e97819978fd183b995f6b7d` adds only the explicit label map and canonicalization. API regression `d0edb517759e3aeaff115e5f449b0f23d1b90cc6` proves `SHA-256` through the authenticated execute route. MD5, SHA-1, SHA-512, generic BLAKE2b, unknown names, and unlisted aliases still fail closed.

The broader generated-PR review finding that the protected Tools page fabricated placeholder `test_value` parameters is owned by the canonical utility-console form lane #1505, which replaces placeholder execution with real user-entered parameter values. This checksum owner does not copy or parallel-write that frontend. Final buyer-visible acceptance therefore requires the utility-console owner path and this checksum owner to coexist on the integrated tree before browser/UI completion can be claimed.

## Standards status reviewed 2026-09-10

The official NIST publication page still lists FIPS 180-4 (2015) as the final Secure Hash Standard. NIST's March 7, 2023 Crypto Publication Review Board decision says FIPS 180-4 will be revised, including removal of the SHA-1 specification, but that decision is a revision plan rather than a replacement final standard. The official NIST/CSRC publication page still lists FIPS 202 (2015) as the final SHA-3 standard and carries a planning note that NIST decided to update it. NIST's March 12, 2025 decision says FIPS 202 will be updated and SP 800-185 revised through the normal draft/public-comment process. A fresh primary-source review on 2026-09-10 found no successor final publication, so Naruon continues to cite the existing final standards while separately recording the announced revisions. RFC 7693 remains the RFC Editor publication describing BLAKE2.

The implementation uses Python's standard-library `hashlib` bindings only; this slice adds no external cryptographic dependency and no model-mediated decision path. Deterministic checksum behavior therefore remains independent of LLM judgment and credentials.

## Research grounding

Two primary peer-reviewed cryptography papers are directly relevant to the non-SHA-2 choices in this bounded surface:

- Bertoni, Daemen, Peeters, and Van Assche (2008) prove the indifferentiability properties of the sponge construction that underpins Keccak/SHA-3. That work supports treating SHA-3 as a distinct, standardized sponge-based hash construction rather than an alias for SHA-2.
- Aumasson, Neves, Wilcox-O'Hearn, and Winnerlein (2013) introduce BLAKE2 and describe BLAKE2b as the 64-bit-oriented variant, including its software-performance and security design goals. That primary design paper is the research basis for exposing BLAKE2b only under an explicit 256-bit output identifier rather than as an ambiguous generic `blake2` option.

No paper PDF is committed in this slice because redistribution permission for the publisher versions was not established from the primary publication records during this review. The citations and DOI links below are therefore the auditable research traceability; this avoids assuming redistribution rights merely because a paper can be viewed online.

## Acceptance evidence

The regression contract covers published/stable `abc` digest vectors for all three algorithms, exact-byte distinction between canonically equivalent Unicode strings, **equivalence between the one-shot tool result and incremental hashing of the identical multilingual UTF-8 byte sequence across chunk boundaries for all three allowed algorithms**, documented display-label normalization to canonical codes, rejection of legacy/out-of-contract names, rejection of text that cannot be represented as valid UTF-8 Unicode scalar values, the one-MiB UTF-8 boundary, authenticated API execution for an advertised label, and idempotent application registration. The chunk-equivalence regression is evidence about digest invariance for identical bytes; it does not introduce or claim a streaming public API. Protected-branch integration still requires exact-current-head CI, security, **100% owned production statement/branch coverage where exposed as required by [ADR-0007](../adr/0007-bounded-content-checksum-surface.md)**, independent review gates, and integration with #1505's real parameter-entry UI before the capability may be described as shipped.

## References (APA 7th)

Aumasson, J.-P., Neves, S., Wilcox-O'Hearn, Z., & Winnerlein, C. (2013). BLAKE2: Simpler, smaller, fast as MD5. In *Applied cryptography and network security* (Lecture Notes in Computer Science, Vol. 7954, pp. 119–135). Springer. https://doi.org/10.1007/978-3-642-38980-1_8

Bertoni, G., Daemen, J., Peeters, M., & Van Assche, G. (2008). On the indifferentiability of the sponge construction. In *Advances in cryptology – EUROCRYPT 2008* (Lecture Notes in Computer Science, Vol. 4965, pp. 181–197). Springer. https://doi.org/10.1007/978-3-540-78967-3_11

National Institute of Standards and Technology. (2015). *Secure hash standard (SHS)* (FIPS PUB 180-4). U.S. Department of Commerce. https://doi.org/10.6028/NIST.FIPS.180-4

National Institute of Standards and Technology. (2015). *SHA-3 standard: Permutation-based hash and extendable-output functions* (FIPS PUB 202). U.S. Department of Commerce. https://doi.org/10.6028/NIST.FIPS.202

National Institute of Standards and Technology. (2022, December 15). *NIST transitioning away from SHA-1 for all applications* (updated February 3, 2025). https://www.nist.gov/news-events/news/2022/12/nist-transitioning-away-sha-1-all-applications

National Institute of Standards and Technology. (2023, March 7). *Decision to revise FIPS 180-4, Secure Hash Standard (SHS)* (updated February 3, 2025). https://www.nist.gov/news-events/news/2023/03/decision-revise-fips-180-4-secure-hash-standard-shs

National Institute of Standards and Technology. (2025, March 12). *Decision to update FIPS 202 and revise SP 800-185*. Computer Security Resource Center. https://csrc.nist.gov/News/2025/decision-to-update-fips-202-and-revise-sp-800-185

Saarinen, M.-J. O., & Aumasson, J.-P. (2015). *The BLAKE2 cryptographic hash and message authentication code (MAC)* (RFC 7693). RFC Editor. https://doi.org/10.17487/RFC7693