# Deterministic utility contracts

This note records the standards basis for Naruon's local `hash_generator`, `url_encoder`, `url_decoder`, and `json_formatter` tools. The utilities do not perform model inference and do not introduce a research algorithm; their contract is therefore grounded in the relevant protocol and security standards rather than an unrelated paper attachment.

## Decisions and traceability

### JSON formatting

RFC 8259 defines JSON object member names as interoperable when they are unique and notes that duplicate names produce unpredictable implementation behavior. It also defines JSON numbers through the JSON grammar; Python's `NaN`, `Infinity`, and `-Infinity` extensions are not portable JSON values. Naruon therefore treats duplicate object names and non-finite numeric constants as invalid instead of silently normalizing them.

- Production: `backend/api/tools.py::json_formatter_handler`, `_strict_json_object`, `_reject_nonfinite_json_constant`
- Regression evidence: `backend/tests/test_utility_tools_contract.py::test_json_formatter_rejects_lossy_or_nonportable_json`
- Failure-channel evidence: `backend/tests/test_utility_tools_contract.py::test_json_formatter_uses_failed_tool_channel_for_invalid_json`

### URL component encoding

RFC 3986 §2.1 defines percent encoding as `%` followed by exactly two hexadecimal digits and explains that reserved characters can be data or delimiters depending on the component. The Naruon tool accepts arbitrary text as one URI component, so reserved characters such as `/` are encoded rather than interpreted structurally. Decoding rejects incomplete/non-hex percent escapes before strict UTF-8 decoding.

- Production: `backend/api/tools.py::url_encoder_handler`, `url_decoder_handler`, `_INVALID_PERCENT_ESCAPE_PATTERN`
- Regression evidence: `backend/tests/test_utility_tools_contract.py::test_url_tools_use_component_semantics_and_round_trip_unicode`, `test_url_decoder_rejects_every_incomplete_or_nonhex_escape`

### Hash generation

SHA-256 and SHA-512 are members of the SHA-2 family standardized by NIST FIPS 180-4. NIST has announced its transition away from SHA-1 for cryptographic protection, and RFC 6151 states that MD5 is not acceptable where collision resistance is required. Naruon keeps MD5 and SHA-1 only as explicit compatibility/checksum choices; the product catalog classifies this feature as a utility and states that those algorithms are not for security-sensitive use. Unknown algorithm names fail rather than falling back to another digest.

- Production: `backend/api/tools.py::hash_generator_handler` and the `hash_generator` `ToolInfo`
- Regression evidence: `backend/tests/test_utility_tools_contract.py::test_hash_generator_supports_explicit_algorithms`, `test_hash_generator_rejects_unknown_algorithm`, `test_hash_generator_catalog_copy_is_not_security_misleading`

## Alternatives rejected

- **Permissive JSON normalization:** rejected because duplicate-key and non-finite-value handling differs across consumers and can lose source meaning.
- **Whole-URL semantics for arbitrary text:** rejected because the tool does not parse a structured URI into components. Treating `/`, `?`, or `#` as caller-supplied structure would make a generic text encoder ambiguous.
- **Silent hash fallback:** rejected because a misspelled algorithm would report success for a digest the caller did not request.
- **Presenting MD5/SHA-1 as security tooling:** rejected because their retained purpose is compatibility/checksumming, not collision-resistant protection.

## References (APA 7th)

Berners-Lee, T., Fielding, R., & Masinter, L. (2005). *Uniform Resource Identifier (URI): Generic syntax* (RFC 3986). Internet Engineering Task Force. https://doi.org/10.17487/RFC3986

Bray, T. (2017). *The JavaScript Object Notation (JSON) data interchange format* (RFC 8259). Internet Engineering Task Force. https://doi.org/10.17487/RFC8259

Dang, Q. H. (2013). Changes in Federal Information Processing Standard (FIPS) 180-4, Secure Hash Standard. *Cryptologia, 37*(1). https://doi.org/10.1080/01611194.2012.687431

National Institute of Standards and Technology. (2015). *Secure Hash Standard (SHS)* (FIPS PUB 180-4). U.S. Department of Commerce. https://doi.org/10.6028/NIST.FIPS.180-4

National Institute of Standards and Technology. (2022, December 15). *NIST transitioning away from SHA-1 for all applications*. https://csrc.nist.gov/news/2022/nist-transitioning-away-from-sha-1-for-all-apps

Turner, S., & Chen, L. (2011). *Updated security considerations for the MD5 message-digest and the HMAC-MD5 algorithms* (RFC 6151). Internet Engineering Task Force. https://doi.org/10.17487/RFC6151
