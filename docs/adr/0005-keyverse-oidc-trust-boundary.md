# ADR-0005: Keyverse OIDC trust boundary

- Status: Accepted
- Date: 2026-08-11

## Context

`keyverse` is the ContextualWisdom ecosystem's central identity provider and
issues OIDC/OAuth credentials to Naruon and related relying parties. Naruon
already contains generic OIDC/JWKS verification, browser PKCE routes, and
strict issuer/JWKS host validation, but the local smoke path can use signed HMAC
sessions and does not start the separate Keyverse repository.

## Decision

- Production and multi-user membership authority uses Keyverse OIDC/JWKS. The
  operator must configure `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`,
  `OIDC_JWKS_URL`, and exact `ALLOWED_OIDC_HOSTS` together.
- The HMAC session path remains a local/control-plane compatibility path for
  smoke tests only. It is not authoritative evidence for cross-workspace or
  security-posture membership.
- Naruon does not copy Keyverse secrets, embed its Keycloak deployment, or
  invent a second identity protocol. The integration stays at the existing
  OIDC/JWKS boundary and must fail closed on partial or unsafe configuration.
- The Keyverse dependency and its readiness/configuration evidence must be
  checked before a production-like browser authentication claim is accepted.

## Consequences

- The local Colima stack remains independently runnable with a fixture HMAC
  session, while production authentication has an explicit external trust
  boundary.
- Keyverse deployment/configuration is an operator concern and is not silently
  replaced by a local fallback.
- OIDC issuer and JWKS DNS/HTTPS/allowlist protections remain mandatory.

## References

- [RFC 8725: JSON Web Token Best Current
  Practices](https://www.rfc-editor.org/rfc/rfc8725.html) (IETF, 2020).
  It requires applications to bind issuer claims to the issuer's cryptographic
  keys and validate the subject; this supports the explicit issuer, JWKS, and
  fail-closed checks at the Keyverse boundary.
- [RFC 9700: Best Current Practice for OAuth 2.0
  Security](https://www.rfc-editor.org/rfc/rfc9700.html) (IETF, 2025).
  It recommends exact redirect handling, PKCE/nonce protections, audience
  restriction, and authorization-server metadata; this supports keeping
  Keyverse as the production identity authority while retaining HMAC only for
  controlled smoke tests.

The source PDFs are not bundled because redistribution rights were not
established; stable links and summaries are provided instead.
