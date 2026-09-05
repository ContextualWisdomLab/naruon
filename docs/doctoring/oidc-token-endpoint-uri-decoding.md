# OIDC token-endpoint URI decoding

Status: Proposed security contract

## Problem

`trustedOidcTokenEndpoint()` validates the configured OIDC token endpoint before any token exchange. ECMAScript `decodeURIComponent()` throws `URIError` for malformed percent escapes. A configured pathname such as `/token/%2` therefore must be treated as invalid endpoint configuration rather than escaping the callback boundary as an uncontrolled runtime exception.

The protected `develop` tree already catches failures from `trustedOidcTokenEndpoint()` and maps them to the redacted `oidc_token_exchange_failed` response. The missing local invariant was that path-segment decoding itself had to convert malformed encoding into that existing configuration-rejection path.

## Decision

The callback path decoder catches decoding failures inside `trustedOidcTokenEndpoint()` and raises the same bounded invalid-path error used for decoded traversal/control-character rejection. The route remains fail closed and preserves the existing HTTPS, issuer-origin, hostname allowlist, private/loopback-host, credential, query/fragment, PKCE-cookie and token-exchange boundaries.

This repair deliberately does not change provider routing, credentials, session validation, cookies, or the external OIDC contract. It also does not weaken the existing path-traversal protections on `develop`.

## Regression

`frontend/src/app/auth/oidc/callback/route.test.ts` sends a callback with `NEXT_PUBLIC_OIDC_TOKEN_ENDPOINT=https://auth.example.com/token/%2` and requires HTTP 502 with `{ "error_code": "oidc_token_exchange_failed" }`. The source change is confined to the path-segment decode boundary in `route.ts`.

Historical PR lineage had accumulated unrelated reversions while repeatedly merging older `develop` states. Those deltas are not part of this security fix. The repaired candidate must be evaluated as current protected `develop` plus the two OIDC source/test deltas and this doctoring record.

## Traceability

- Product source: `frontend/src/app/auth/oidc/callback/route.ts`
- Regression: `frontend/src/app/auth/oidc/callback/route.test.ts`
- Original RED/fix provenance: commit `7a0b0e443ae31a941c5a2139a2093b1af876458c`
- Protected baseline at repair: `develop@042b0c70531b229af3acbd0421a2f23098d848b3`

## References

Ecma International. (2025). *ECMA-262, 16th edition: ECMAScript 2025 language specification* (Sec. 19.2.6, URI handling functions). https://tc39.es/ecma262/2025/multipage/global-object.html

OWASP Foundation. (n.d.). *Denial of service*. Retrieved September 5, 2026, from https://owasp.org/www-community/attacks/Denial_of_Service
