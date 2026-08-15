# DAV single-decode and local LLM-provider network boundaries

## Decision

Naruon treats the framework-decoded DAV application path as the authorization input. Authorization does not recursively decode the same string. Residual percent encodings are preserved when they remain literal data, and fail closed when another decode could introduce path separators, traversal dots, backslashes, C0/DEL controls, or NUL. This keeps routing, owner checks, logging, and DAV handlers on one canonical path representation.

For local LLM runtimes, `ALLOW_LOCAL_LLM_PROVIDERS` is an explicit development/deployment opt-in rather than a general exception from SSRF controls. Loopback addresses remain permitted only under that opt-in. An exact operator-allowlisted single-label provider hostname may additionally resolve only into the private address families intended for site/container networking: RFC 1918 IPv4 private-use networks or RFC 4193 IPv6 unique-local addresses. The allowlist does not authorize IPv4 link-local/metadata space, multicast, unspecified, reserved, broadcast, or other special-purpose non-global address classes.

## Why this boundary is narrower than `is_private`

Python's IP classification helpers intentionally aggregate several non-global categories for convenience. Product authorization needs a positive description of the address classes that are actually required. RFC 1918 defines the three private IPv4 blocks used by private internets, and RFC 4193 defines IPv6 unique-local addresses for local communications. By contrast, RFC 3927 defines IPv4 link-local `169.254.0.0/16`, and RFC 6890 records special-purpose registry properties such as whether a block is globally reachable or forwardable. Therefore an operator hostname allowlist cannot safely mean "accept every address for which a library reports non-global/private".

This positive-network contract also preserves the existing DNS-pinning design: every resolved address is validated against the same hostname-scoped policy before it can enter the pinned transport, and the transport revalidates the address again before connecting.

## Verification contract

The security regression suite must prove all of the following:

- an exact allowlisted local provider plus explicit local-provider opt-in can reach RFC 1918 container/private addresses;
- local-provider opt-in without exact hostname allowlisting does not admit RFC 1918 addresses;
- loopback remains conditional on the explicit local-provider opt-in;
- an allowlisted local provider still rejects `169.254.169.254`, multicast, unspecified, broadcast/reserved, and other non-authorized special-purpose classes;
- the DAV path contract rejects ambiguous residual structural encodings without recursively transforming literal percent data;
- the canonical DAV path is the same value used by authorization and downstream routing.

The current slice does not claim that private-network access is generally safe, that DNS alone is an authorization mechanism, or that these controls replace tenant authorization, TLS identity, credential isolation, outbound method/path policy, or provider-specific authentication.

## Rollback

If local-provider compatibility requires another address family, do not widen the exception to all non-global addresses. Add the smallest explicit network class only after a concrete deployment requirement, threat analysis, tests, and operator-visible configuration contract are established. If the DAV canonicalization contract changes, update authorization and route-level tests together so parsing and authorization cannot diverge.

## References (APA 7th)

Berners-Lee, T., Fielding, R., & Masinter, L. (2005). *Uniform Resource Identifier (URI): Generic syntax* (RFC 3986). RFC Editor. https://doi.org/10.17487/RFC3986

Cheshire, S., Aboba, B., & Guttman, E. (2005). *Dynamic configuration of IPv4 link-local addresses* (RFC 3927). RFC Editor. https://doi.org/10.17487/RFC3927

Cotton, M., Vegoda, L., Bonica, R., & Haberman, B. (2013). *Special-purpose IP address registries* (BCP 153, RFC 6890). RFC Editor. https://doi.org/10.17487/RFC6890

Hinden, R., & Haberman, B. (2005). *Unique local IPv6 unicast addresses* (RFC 4193). RFC Editor. https://doi.org/10.17487/RFC4193

Rekhter, Y., Moskowitz, B., Karrenberg, D., de Groot, G. J., & Lear, E. (1996). *Address allocation for private internets* (BCP 5, RFC 1918). RFC Editor. https://doi.org/10.17487/RFC1918
