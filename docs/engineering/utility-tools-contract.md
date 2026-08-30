# Utility Tools Contract

The tools console is an interactive boundary: it submits the values entered by
the user for each registered parameter. Empty string values are intentional;
the console does not submit a canned sample value.

The five text utilities enforce a 100,000-character input limit at the shared
tool-parameter validation boundary. The JSON formatter preserves the original
lexical form of valid JSON numbers, rejects duplicate object names and
non-standard numeric constants, and only changes whitespace. The URL decoder
rejects percent-encoded byte sequences that are not valid UTF-8 instead of
silently replacing them.

## Standards and research basis

| Contract decision | Basis and applicability |
|---|---|
| URL encoding and decoding use the URI percent-encoding model | RFC 3986 defines the generic URI syntax and percent-encoded octets. The encoder therefore encodes all non-unreserved input, while the decoder treats malformed UTF-8 as invalid input. |
| JSON numbers are not converted through binary floating point | RFC 8259 defines JSON number syntax but does not require a binary floating-point representation. Retaining the parsed token makes formatting whitespace-only for long decimals, large exponents, integers, and nested values. |
| Duplicate JSON names are rejected | RFC 8259 recommends unique object names and notes that implementations differ when names are repeated. Rejecting duplicates is the deterministic, loss-avoiding contract for this formatter. |
| Utility inputs have explicit length bounds | OWASP recommends allowlist validation and length limits at trust boundaries. The shared 100,000-character ceiling bounds memory amplification from encoding, escaping, and pretty-printing. |

## References (APA 7)

Bray, T. (2017). *The JavaScript Object Notation (JSON) data interchange
format* (RFC 8259). Internet Engineering Task Force.
https://www.rfc-editor.org/rfc/rfc8259

Internet Engineering Task Force. (2005). *Uniform Resource Identifier (URI):
Generic syntax* (RFC 3986). https://www.rfc-editor.org/rfc/rfc3986

OWASP Foundation. (n.d.). *Input validation cheat sheet*. Retrieved August 30,
2026, from
https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html

