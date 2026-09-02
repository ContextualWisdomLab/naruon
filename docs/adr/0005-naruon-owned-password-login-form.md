# ADR-0005: naruon renders its own login form; Keyverse stays the identity backend

**Status:** Accepted (Naruon-local integration policy)
**Date:** 2026-09-02
**Decision owner:** Naruon maintainers, per explicit product direction
**Scope:** How naruon's browser-facing login form is rendered and which
Keyverse mechanism authenticates it. Does not change Keyverse's role as
identity backend, does not disable the existing federated-SSO redirect path,
and does not authorize naruon to store or validate credentials on its own.

## Context

Naruon's login previously had one entry point for Keyverse authentication:
Settings → Security → "OIDC 로그인," which called
`window.location.assign(authorizationUrl)` — a full top-level browser
navigation to Keycloak's own hosted `/protocol/openid-connect/auth` page
(standard OIDC Authorization Code + PKCE flow). Verified directly in
`frontend/src/lib/oidc-session.ts` and
`frontend/src/app/auth/oidc/login/route.ts` before any change was made.

Product direction asked for naruon's own branding on that form. An initial
Keycloak-custom-theme reskin was built and screenshot-verified working
(theme.properties extending Keycloak's `keycloak` base theme, CSS matching
naruon's palette, correctly rendering naruon's logo and colors on the real
`/protocol/openid-connect/auth` page). The product owner rejected this
approach outright on review: *"아니 그리고 누가 Naruon을 Theme 붙이겠대"*
("who ever said [they wanted] a Theme attached to naruon"). A reskinned
Keycloak theme is still Keycloak's own server rendering the HTML the
browser receives — exactly what was not wanted, disguised or not. The
re-confirmed requirement: naruon's own frontend renders 100% of the
login/signup UI, with **zero Keycloak-rendered HTML anywhere in the loop**,
and naruon's own backend talks to Keyverse purely as an API.

### Passwordless was investigated first, not assumed away

Before choosing a password-based mechanism, whether Keyverse's WebAuthn
passwordless capability could satisfy a naruon-owned form was checked
directly against `keyverse`'s own repository, not assumed:

- `keyverse/docs/passwordless-policy.md` and `keyverse/docs/adr/0002-passwordless-local-accounts.md`
  confirm the `cwl` realm's `browserFlow` (`browser-passwordless`) has *no
  password authenticator anywhere*, enforced in CI by
  `keyverse/scripts/validate_realm.py`.
- Keycloak's WebAuthn *authentication* ceremony (as opposed to registration)
  runs inside Keycloak's own `login-actions` flow, bound to a server-side
  `AuthenticationSessionModel` that generates the challenge and later
  verifies the posted assertion. Keycloak does not publish a public REST
  pair ("give me a challenge" / "here is my assertion") for that ceremony
  outside the flow it owns. This is confirmed against Keycloak's WebAuthn
  implementation, not a Keyverse gap: even Keyverse's own passwordless
  *registration* path ends the same way — after
  `POST /registration/accounts`, the emailed `execute-actions-email` link
  lands the user on a Keycloak-hosted required-action page to run
  `webauthn-register-passwordless`, before redirecting back to naruon's
  `/auth/passkey-complete`. Only the redirect target is naruon's; the
  ceremony page itself is Keycloak's.
- Conclusion: a fully naruon-rendered WebAuthn login is not achievable
  against Keycloak's current, unmodified architecture. It would need a
  custom Keycloak REST resource provider reimplementing the ceremony's
  session/challenge handling — real, separate engineering on the Keyverse
  side, not a naruon-side or configuration-only change.

### Direct Access Grants is the mechanism that actually fits

Direct Access Grants (OAuth2 §4.3 Resource Owner Password Credentials) is
the only mechanism Keycloak exposes as a plain, stateless, public REST
endpoint (`/protocol/openid-connect/token`, `grant_type=password`) — which
is exactly what "naruon's own form, naruon's own backend, zero Keycloak
HTML" requires. It is also the option this ecosystem has worked hardest to
avoid: `docs/CWL-MASTER-CONTEXT.md` states "central passwordless IdP ...
eliminate passwords" as a binding organizational principle, and Keyverse's
own ADR-0002 requires "explicit security/product review and migration
evidence" to add a password path back for local accounts.

The product owner acknowledged this tension directly and accepted it for
this one integration, explicitly: naruon's process may transiently hold a
plaintext password in memory for the single request that forwards it to
Keycloak's token endpoint, provided it is never logged, cached, or
persisted. Keyverse's own ADR
([keyverse#0014](https://github.com/ContextualWisdomLab/keyverse/blob/main/docs/adr/0014-naruon-owned-password-form.md))
records the matching keyverse-side decision: `naruon-web`'s
`directAccessGrantsEnabled` is `true`, scoped to that one client only, while
every other/future RP stays hard-blocked by account-unification's dynamic
registration validator.

## Decision

1. naruon renders its own email/password login form (Settings → Security →
   "Naruon 계정으로 로그인"). Submitting it calls naruon's own backend route,
   never a Keycloak URL, never a redirect.
2. `frontend/src/app/auth/password/login/route.ts` performs the grant
   server-side: it builds `grant_type=password` + `client_id=naruon-web` +
   the submitted credentials and POSTs it to Keycloak's token endpoint using
   the same SSRF-hardened, DNS-pinned token client
   (`@/lib/oidc-token-client`) and the same trusted-endpoint validation
   (`trustedOidcTokenEndpoint`, extracted to `../oidc/shared.ts` so both the
   authorization-code callback and this route share one hardened
   implementation) already used for the authorization-code exchange. On
   success it mints the same `naruon_session` HttpOnly cookie the existing
   flow uses, after the same backend session-claims verification
   (`backendAcceptsSessionToken`).
3. The password is never logged. Failures are recorded through
   `recordOidcTokenExchangeFailure`, which only ever receives a fixed reason
   string, never request data. A wrong password, an unknown user, and a
   client without Direct Access Grants enabled are all collapsed into one
   generic `password_login_invalid_credentials` (HTTP 401) response, so the
   error surface cannot be used to enumerate users or probe configuration.
4. The existing federated-SSO redirect path (Settings → Security →
   "Keyverse SSO로 로그인," renamed from "OIDC 로그인" for clarity now that
   two mechanisms coexist) is **kept, not removed**. It remains the only way
   to authenticate a federated identity (employer ADFS, other brokered
   IdPs), which has no local password to submit via Direct Access Grants.
   The naruon-owned popup-based redirect improvement made earlier in this
   same effort (`startOidcLogin` opens Keycloak's page in a popup instead of
   navigating naruon's own tab away) still applies to that path — it does
   not, by itself, satisfy the zero-Keycloak-HTML requirement (the popup
   still shows a Keycloak-rendered page), so it was not treated as a
   substitute for this ADR's decision, only kept as a real, independent
   improvement to the federation path that remains necessary.

## What this does not yet deliver

**Update (2026-09-02): login and signup now both work end-to-end.** The gap
described below — no `cwl`-realm account had a password credential, so every
Direct Access Grants attempt failed closed — is closed by a companion
Keyverse change,
[keyverse#0015](https://github.com/ContextualWisdomLab/keyverse/blob/main/docs/adr/0015-naruon-password-credential-issuance.md):
`POST /registration/accounts/password`, a scoped account-unification
endpoint (gated by its own third bearer token, naruon-only) that creates a
`cwl` user with an immediately usable password credential. naruon's signup
form ("Naruon 계정 만들기") calls it through a new
`frontend/src/app/auth/password/signup/route.ts`, then immediately reuses
`exchangePasswordForSessionResponse` (the same exchange login uses) so
signup ends with a signed session, not a second manual login step.

What is still genuinely deferred, per keyverse#0015: email verification
(accounts are created with `emailVerified: false` and no verification
required action), CAPTCHA-equivalent abuse hardening beyond a per-peer rate
limit, self-service password reset, and merging a password-created identity
with an existing passwordless one for the same person. naruon's signup form
copy states this plainly to the user rather than implying full production
completeness.

The paragraph below is kept for the historical record of what this ADR's
first slice did and did not deliver before keyverse#0015 landed.

Login did not work end-to-end at first. No account in Keyverse's `cwl` realm
had a password credential — `POST /registration/accounts` explicitly
refuses to accept or create one, and self-service password reset stays off.
Every Direct Access Grants attempt against the realm failed closed with a
generic invalid-credentials error, correctly, because there was nothing to
authenticate against — not because naruon's integration was wrong. Making
this functional needed one more, separately-reviewable Keyverse change (a
credential-issuance path) that keyverse#0014 explicitly deferred as its own,
bigger, separately-reviewable follow-up — the follow-up keyverse#0015 is.

## Alternatives rejected

### Keycloak custom theme (reskin, not bypass)

Built and screenshot-verified working, then explicitly rejected by the
product owner: still Keycloak's own server producing the response,
regardless of how closely it is styled to match naruon. Not a compromise
worth keeping as a fallback — the requirement is about which server renders
the page, not how it looks.

### Silent/popup Keycloak redirect

Improves the *feel* of the existing federated path (the naruon tab no
longer navigates away) but does not change which server renders the login
UI — the popup still shows Keycloak's page. Kept as an improvement to the
federated-SSO path specifically, not treated as satisfying this decision.

### naruon-rendered WebAuthn ceremony

Investigated and ruled out as a structural Keycloak-architecture
limitation, not a configuration gap — see Context.

## Consequences

- naruon now has two authentication paths on one client (`naruon-web`),
  serving different account types: Direct Access Grants for naruon-native
  local accounts, and the authorization-code redirect for federated
  identity. Both remain visible in Settings → Security.
- naruon's frontend/backend now transiently touches plaintext passwords —
  an explicit, reviewed, accepted exception to this org's stated
  passwordless direction for this one integration, not a general policy
  change. `frontend/src/app/auth/password/login/route.ts` and
  `frontend/src/components/SettingsLayout.tsx`'s password form are the only
  places a raw password exists in naruon's code, and neither logs nor
  persists it.
- The credential-issuance gap (no password-capable registration exists yet)
  means this slice ships real, tested, correct client code that is honestly
  non-functional against the current Keyverse deployment until keyverse#0014's
  follow-up lands. This is recorded here rather than papered over.

## References

Hardt, D. (Ed.). (2012). *The OAuth 2.0 authorization framework* (RFC 6749),
§4.3 Resource Owner Password Credentials Grant.
https://doi.org/10.17487/RFC6749

Hodges, J., Jones, J. C., Jones, M. B., Kumar, A., & Lundberg, E. (Eds.).
(2021, April 8). *Web Authentication: An API for accessing Public Key
Credentials Level 2* (W3C Recommendation), §7 WebAuthn Relying Party
Operations. https://www.w3.org/TR/2021/REC-webauthn-2-20210408/
