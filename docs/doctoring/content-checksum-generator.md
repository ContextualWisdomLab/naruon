# Content checksum generator — standards and product boundary

**Status:** active PR candidate; not shipped until merged through protected `develop`.

**Traceability:** bounded checksum slice of issue #1247, *Build an auditable data-hygiene utility suite*.

## Product contract

Naruon's `content_checksum_generator` compares the exact UTF-8 byte sequence supplied by the caller. It deliberately does **not** Unicode-normalize input before hashing, because normalization would change the byte-level evidence being compared. The deterministic tool accepts at most 1,048,576 UTF-8 bytes per invocation and exposes only these normal-surface algorithms:

- `sha256` — SHA-256 from FIPS 180-4;
- `sha3_256` — SHA3-256 from FIPS 202;
- `blake2b_256` — BLAKE2b with a 256-bit digest, using the BLAKE2 construction standardized in RFC 7693.

MD5 and SHA-1 are intentionally absent from the normal surface. NIST states that SHA-1 is being transitioned out for applying cryptographic protection by December 31, 2030; Naruon therefore does not introduce SHA-1 as a new customer-facing checksum choice. No legacy-compatibility checksum mode is part of this slice.

A returned digest is an equality/integrity fingerprint for the exact supplied bytes. It does not authenticate a sender, prove provenance, or replace a keyed MAC or digital signature. Customer-facing output carries that warning with every result so the next action is explicit: compare the digest with an independently obtained expected digest when checking content equality; use an authenticated construction when sender or origin authenticity matters.

## Standards status reviewed 2026-08-15

FIPS 180-4 remains NIST's final Secure Hash Standard publication while NIST has announced a future revision. FIPS 202 remains NIST's final SHA-3 standard while NIST has announced an update process. These planning notes are not treated as replacement standards before a successor is finalized. RFC 7693 is the RFC Editor publication describing BLAKE2.

The implementation uses Python's standard-library `hashlib` bindings only; this slice adds no external cryptographic dependency and no model-mediated decision path. Deterministic checksum behavior therefore remains independent of LLM judgment and credentials.

## Acceptance evidence

The regression contract covers published/stable `abc` digest vectors for all three algorithms, exact-byte distinction between canonically equivalent Unicode strings, rejection of SHA-1/MD5 and ambiguous aliases, the one-MiB UTF-8 boundary, and idempotent application registration. Protected-branch integration still requires exact-current-head CI, security, coverage, and independent review gates before the capability may be described as shipped.

## References (APA 7th)

National Institute of Standards and Technology. (2015). *Secure hash standard (SHS)* (FIPS PUB 180-4). U.S. Department of Commerce. https://doi.org/10.6028/NIST.FIPS.180-4

National Institute of Standards and Technology. (2015). *SHA-3 standard: Permutation-based hash and extendable-output functions* (FIPS PUB 202). U.S. Department of Commerce. https://doi.org/10.6028/NIST.FIPS.202

National Institute of Standards and Technology. (2022, December 15). *NIST transitioning away from SHA-1 for all applications* (updated February 3, 2025). https://www.nist.gov/news-events/news/2022/12/nist-transitioning-away-sha-1-all-applications

Saarinen, M.-J. O., & Aumasson, J.-P. (2015). *The BLAKE2 cryptographic hash and message authentication code (MAC)* (RFC 7693). RFC Editor. https://doi.org/10.17487/RFC7693
