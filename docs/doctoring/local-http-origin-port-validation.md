# Local HTTP origin port-validation boundary

## Decision

`validate_loopback_http_origin()` distinguishes an absent URI port from an explicitly supplied port value. Scheme defaults are applied only when the port subcomponent is absent. An explicit port `0`, a value outside the application's `1..65535` transport-port contract, or a malformed/non-numeric port is rejected rather than rewritten to the scheme default.

This is an origin-integrity rule, not only input cleanup. A caller that supplied `:0` expressed a materially different authority from one that omitted the port. Replacing the explicit value with `80` or `443` changes caller intent and can convert malformed or attacker-controlled configuration into a valid local destination.

The same validator continues to require the existing loopback-host allowlist and to reject credentials, path/query/fragment material outside the local-origin contract, control characters, and unsafe request-target traversal.

## Standards basis

RFC 3986 defines the URI authority as host plus an optional decimal port subcomponent and allows a scheme to define a default port. The default therefore belongs to the *absent-port* case; an explicitly parsed port must not be collapsed with absence merely because the application's language treats numeric zero as false.

RFC 6335 defines the Service Name and Transport Protocol Port Number Registry and the port-number space used by transport protocols. Naruon's local-origin helper intentionally narrows its application contract to `1..65535`; port zero is not a usable destination for this product path. The validator preserves this product-level restriction without making a broader claim that RFC 3986 itself forbids the textual URI `:0`.

## Verification contract

Regression tests keep scheme defaults, explicit supported ports, explicit `:0`, range errors, malformed ports, loopback canonicalization, userinfo, path/query/fragment, controls, and non-allowlisted hosts distinct.

## References (APA 7th)

Berners-Lee, T., Fielding, R., & Masinter, L. (2005). *Uniform Resource Identifier (URI): Generic syntax* (RFC 3986). RFC Editor. https://doi.org/10.17487/RFC3986

Cotton, M., Eggert, L., Touch, J., Westerlund, M., & Cheshire, S. (2011). *Internet Assigned Numbers Authority (IANA) procedures for the management of the service name and transport protocol port number registry* (BCP 165, RFC 6335). RFC Editor. https://doi.org/10.17487/RFC6335
