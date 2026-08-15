# HTTP invalid-session throttling evidence

## Decision

Naruon's HTTP authentication boundary applies two bounded failed-verification budgets:

1. an exact-token budget keyed by a SHA-256 digest of the bearer token; and
2. a coarser peer budget keyed by a SHA-256 digest of the server-observed ASGI `request.client.host` value.

The application does not derive the peer budget from `Forwarded`, `X-Forwarded-For`, or other caller-controlled forwarding headers. Deployments behind a trusted reverse proxy must configure the proxy/server boundary so the ASGI client address has the intended operational meaning. The peer budget is deliberately looser than the exact-token budget because NAT gateways and reverse proxies can make many legitimate users share one observed peer.

A failed HTTP verification increments both budgets. A successful verification clears only the exact-token failure bucket. The peer bucket expires naturally and is not reset by possession of a valid token, preventing a valid session from becoming an attacker-controlled reset primitive. Direct non-HTTP `build_auth_context()` calls retain only the exact-token budget because no trustworthy HTTP peer scope exists at that boundary.

Both key families share the existing bounded in-memory bucket store, expiry window, and capacity limit. This coarse peer signal is defense in depth against varying invalid tokens; it is not a substitute for subscriber/authenticator-specific controls, identity-provider throttling, network perimeter controls, or tenant authorization.

## Evidence and interpretation

NIST SP 800-63B-4 requires verifiers to implement controls against online guessing and explicitly identifies IP address, geolocation, timing, and browser metadata as signals that can inform adaptive protections. Naruon uses the server-observed peer address only as one coarse abuse signal and keeps its existing cryptographic verification and exact-token budget. Because this peer signal can represent multiple users behind NAT or a reverse proxy, the product applies a higher threshold and bounded expiry rather than treating the address as subscriber identity.

RFC 7519 defines JWT bearer-token claims and NumericDate semantics but does not make unsigned or unverified token contents trustworthy identity. Naruon therefore does not use an unverified `sub`, `iss`, `aud`, or other JWT claim to choose the aggregate throttle identity. OIDC issuer and audience validation remains a separate post-signature trust boundary.

OpenID Connect Core requires the ID Token issuer to exactly match the issuer identifier and requires the relying party's `client_id` to be present in the `aud` claim; `aud` may be multi-valued. Naruon's Keyverse OIDC path therefore keeps exact issuer validation while accepting the configured client identifier as a member of the verified audience claim.

## Verification contract

Regression tests must prove that:

- varying invalid bearer tokens from one server-observed HTTP peer exhaust one aggregate budget;
- changing `Forwarded` or `X-Forwarded-For` does not create a new application-level peer identity;
- independent trusted peer scopes retain independent budgets;
- a valid token cannot reset the coarse peer failure budget;
- the direct non-HTTP authentication entry point retains its exact-token-only contract; and
- failure-bucket memory remains bounded and time-limited.

## References

National Institute of Standards and Technology. (2025). *Digital identity guidelines: Authentication and authenticator management (NIST Special Publication 800-63B-4).* U.S. Department of Commerce. https://doi.org/10.6028/NIST.SP.800-63B-4

Jones, M., Bradley, J., & Sakimura, N. (2015). *JSON Web Token (JWT)* (RFC 7519). Internet Engineering Task Force. https://doi.org/10.17487/RFC7519

OpenID Foundation. (2014). *OpenID Connect Core 1.0 incorporating errata set 1*. https://openid.net/specs/openid-connect-core-1_0.html
