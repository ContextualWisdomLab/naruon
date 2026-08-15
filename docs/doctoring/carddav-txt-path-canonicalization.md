# CardDAV TXT path canonicalization

## Scope

Naruon consumes the optional `path` key advertised by a secure `_carddavs._tcp` TXT record during CardDAV discovery. The value becomes part of an outbound HTTPS request target, so validation and execution must use one unambiguous representation.

## Decision

The parser applies the following fail-closed contract:

1. Reject malformed percent triplets before decoding.
2. Percent-decode the TXT value exactly once with strict UTF-8 handling.
3. Reject the value when a valid percent triplet remains after that pass, because a second decoder could observe a different request target.
4. Reject traversal segments, backslashes, query or fragment delimiters, absolute-URI syntax, and Unicode control characters.
5. Return and execute the same validated representation.

This replaces the previous arbitrary five-round recursive decoding budget. Recursive decoding changed legitimate literal-percent paths and left the security meaning dependent on a chosen iteration count. A single-pass contract follows the URI processing rule that a component must not be percent-decoded more than once, while rejecting nested encodings that would remain ambiguous at another HTTP or provider boundary.

An encoded literal percent remains supported when its decoded form does not begin another percent triplet. Invalid UTF-8 is rejected rather than normalized through the Unicode replacement character.

## Product boundary

This decision protects CardDAV auto-discovery only. It does not grant authorization to arbitrary paths, weaken the existing HTTPS/global-address SSRF controls, or treat TXT records as trusted credentials. Provider account authorization and resource ownership remain separate checks.

## Verification

The focused regression suite covers:

- a singly encoded leading slash;
- Korean UTF-8 path text;
- nested encoded slash and traversal forms;
- nested encoded percent forms;
- incomplete and non-hex percent triplets;
- invalid UTF-8 octets;
- a safe encoded literal percent.

## References

Berners-Lee, T., Fielding, R., & Masinter, L. (2005). *Uniform resource identifier (URI): Generic syntax* (RFC 3986). RFC Editor. https://doi.org/10.17487/RFC3986

Daboo, C. (2012). *Locating CalDAV and CardDAV services* (RFC 6764). RFC Editor. https://doi.org/10.17487/RFC6764

MITRE. (2025). *CWE-174: Double decoding of the same data*. Common Weakness Enumeration. https://cwe.mitre.org/data/definitions/174.html
