# ADR-0005: Naruon-owned authentication UI with Keyverse identity authority

**Status:** Proposed — merge blocked on standards-compliant Keyverse contract
**Date:** 2026-09-02
**Last reviewed:** 2026-09-03
**Decision owner:** Naruon maintainers for product UI; Keyverse for identity/authentication protocol
**Scope:** Browser-facing authentication UX and the Naruon↔Keyverse boundary. Naruon does not become an identity provider and does not own credential validation.

## Problem

Naruon must render its own login, signup, and recovery product surfaces. Replacing Keycloak CSS or theme assets does not satisfy that requirement because Keycloak still renders the authentication page. At the same time, the mechanism behind a Naruon-rendered form must satisfy current OAuth/OIDC security requirements and must not copy Keyverse domain truth or consume a mutable Keyverse branch as a production contract.

The existing federated path is Authorization Code + PKCE and remains valid. A separate experimental password path was added to this PR using Keycloak Direct Access Grants (`grant_type=password`) because it allowed a Naruon-rendered form without Keycloak HTML. That implementation is useful evidence about the desired product boundary, but it is not an acceptable merge target.

## Standards finding

RFC 9700 §2.4 is normative Best Current Practice and states that the Resource Owner Password Credentials grant **MUST NOT** be used. The reason is structural: the client receives the resource owner's password, expands the credential attack surface, and prevents or complicates modern multi-step and cryptographic authentication.

RFC 10017 §7.3, published in August 2026 for browser-based applications, repeats that ROPC **MUST NOT** be used. For browser applications using OAuth or OpenID Connect, it requires a redirect-based flow such as Authorization Code. A local product decision or accepted-risk note cannot convert a `MUST NOT` mechanism into a conforming implementation.

Therefore the earlier rationale that Direct Access Grants was "the mechanism that actually fits" is superseded. It fits the rendering constraint but violates the protocol/security constraint. This ADR remains Proposed until Keyverse publishes a standards-compliant, versioned headless authentication/session contract that can preserve Naruon's product-owned UI without reintroducing ROPC.

## Current decision

1. **Naruon owns the product surfaces.** Login, signup, recovery, loading, error, permission, responsive, keyboard, and accessibility states are Naruon UI responsibilities.
2. **Keyverse remains identity authority.** Naruon must not copy Keyverse credential rules, user-store semantics, authentication-session state machines, or provider-specific domain truth.
3. **The existing Authorization Code + PKCE federation path remains supported.** The popup variant is an interaction improvement, not a new authentication protocol. The popup is reserved before asynchronous initialization so transient browser user activation is preserved; completion uses a flow-scoped same-origin `BroadcastChannel`, and the authorization page does not retain a live `window.opener` relationship.
4. **ROPC/password-grant code in this Draft PR is transitional evidence only.** It must not be merged or released as the GA authentication path. A product-owner exception is recorded as historical context, not as a standards waiver.
5. **A Keyverse replacement is a prerequisite.** The canonical owner must provide and immutably release a headless authentication/session capability suitable for the Naruon-owned surface. Naruon may consume only the released contract through an ACL; an open Keyverse PR or branch head is not a production dependency.
6. **Secrets remain behind Naruon credential infrastructure.** Runtime application secrets must not become a new `process.env` contract. Environment variables are bootstrap transport only under the repository's `AGENTS.md`; any long-lived Keyverse registration credential must be retrieved through the protected credential registry/backend boundary before this PR can become Ready.

## Security repairs already made in this Draft

These repairs are independently useful and should be preserved by any successor even though they do not make ROPC acceptable:

- OIDC popup reservation occurs before the first asynchronous login-initialization wait, preserving transient user activation. Popup-blocked browsers fall back to top-level navigation; a failed initialization closes the reserved blank window.
- The authorization popup is opener-severed and result correlation is flow-specific.
- Password signup uses same-origin CSRF checks and bounded request parsing.
- Upstream account-unification 422 details are translated through a Naruon-owned public error taxonomy instead of leaking mutable provider strings as Naruon API contracts.
- Account-unification registration traffic no longer relies on hostname validation followed by an unpinned `fetch`. The password-bearing request resolves the destination, rejects any non-global answer outside the explicit development-loopback exception, and pins the native HTTP(S) socket lookup to the validated address set. Redirects fail closed and responses are size bounded.

These statements describe source changes in the Draft branch; they are not release claims until exact-head CI, security checks, browser/E2E evidence, review, and protected merge complete.

## Remaining blockers

### Standards-compliant authentication contract

The current password login/session exchange still uses `grant_type=password`. This is the primary architecture blocker. Keyverse must replace it with a released contract that satisfies RFC 9700 and RFC 10017 while allowing the application-owned product surface. Until that exists, the password path stays Draft and must not be enabled in production.

### Mutable/unreleased dependency

The companion Keyverse work referenced by this PR is open/unreleased. Its source head cannot be consumed as a canonical production contract, and this ADR must not say the signup capability "landed" or works end-to-end in a released deployment until immutable publication evidence exists.

### Secret ownership

`ACCOUNT_UNIFICATION_PASSWORD_REGISTRATION_TOKEN` is still read from the frontend server runtime environment in the current Draft. This violates the Naruon repository rule that new runtime application secrets belong in the protected credential registry. Deployment documentation or an `.env` example would not repair that boundary.

### Signup atomicity

Account creation currently precedes session establishment. If account creation succeeds and the subsequent session step fails, the user can see a generic signup failure even though the account now exists, and retry can produce an email-taken conflict. The replacement Keyverse contract needs idempotent/continuation semantics or an explicit typed partial-success outcome; Naruon must not invent a compensating delete across the identity boundary.

### Authenticated settings refresh

Some Settings data can fail while anonymous. A successful login currently refreshes session claims but does not necessarily re-fetch all permission-sensitive settings resources, leaving stale failure state until reload. The authenticated refresh path needs a component-level regression test and causal repair.

### Verification

This Draft still requires current-head unit/type/lint/build evidence, security/SAST/CodeQL evidence, browser E2E for login/signup/recovery and popup-blocked flows, locale/a11y evidence where material, resolved review threads, and the repository's independent approval/required-check gates. Hosted workflow queuing or startup failure is not GREEN evidence.

## Alternatives

### Keycloak theme

Rejected for the product requirement. It can alter appearance but Keycloak still renders the authentication surface.

### Authorization popup only

Kept for federation. It preserves Naruon's primary tab and can be implemented safely, but the popup still contains authorization-server UI and therefore does not by itself satisfy the requirement for a fully Naruon-rendered local-account surface.

### Direct Access Grants / ROPC

Rejected as the merge architecture. It satisfies the zero-Keycloak-HTML rendering constraint but violates RFC 9700 §2.4 and RFC 10017 §7.3.

### Naruon reimplementation of Keycloak/WebAuthn internals

Rejected. Reimplementing Keyverse/Keycloak authentication-session or WebAuthn ceremony semantics inside Naruon would duplicate the identity bounded context and create a second security authority. The capability belongs in Keyverse behind a released contract.

## Effects

The desired product boundary remains unchanged: Naruon presents the user experience, while Keyverse owns identity authentication. What changes is the accepted implementation path. The Draft's password-grant mechanism is now explicitly non-releasable, and the PR cannot become Ready merely because product stakeholders accept its risk.

Any successor must preserve the independent security fixes above, replace ROPC with the immutable Keyverse contract, remove the runtime-secret environment dependency, define signup partial-success semantics, rehydrate permission-sensitive settings after authentication, and then obtain exact-head evidence before merge.

## References

Lodderstedt, T., Bradley, J., Labunets, A., & Fett, D. (2025). *Best current practice for OAuth 2.0 security* (RFC 9700, BCP 240). RFC Editor. https://doi.org/10.17487/RFC9700

Parecki, A., De Ryck, P., & Waite, D. (2026). *OAuth 2.0 for browser-based applications* (RFC 10017, BCP 212). RFC Editor. https://doi.org/10.17487/RFC10017

Hardt, D. (Ed.). (2012). *The OAuth 2.0 authorization framework* (RFC 6749). RFC Editor. https://doi.org/10.17487/RFC6749

World Wide Web Consortium. (2021). *Web Authentication: An API for accessing Public Key Credentials Level 2*. https://www.w3.org/TR/webauthn-2/
