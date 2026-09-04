# ADR-0005: Naruon-owned authentication UI with Keyverse identity authority

**Status:** Proposed — merge blocked on standards-compliant Keyverse contract
**Date:** 2026-09-02
**Last reviewed:** 2026-09-04
**Decision owner:** Naruon maintainers for product UI; Keyverse for identity/authentication protocol
**Scope:** Browser-facing authentication UX and the Naruon↔Keyverse boundary. Naruon does not become an identity provider and does not own credential validation.

## Problem

Naruon must render its own login, signup, and recovery product surfaces. Replacing Keycloak CSS or theme assets does not satisfy that requirement because Keycloak still renders the authentication page. At the same time, the mechanism behind a Naruon-rendered form must satisfy current OAuth/OIDC security requirements and must not copy Keyverse domain truth or consume a mutable Keyverse branch as a production contract.

The existing federated path is Authorization Code + PKCE and remains valid. An experimental password path was added to this Draft using Keycloak Direct Access Grants (`grant_type=password`) because it allowed a Naruon-rendered form without Keycloak HTML. That experiment established useful product-boundary evidence, but it is not an acceptable merge target and its public Naruon routes now fail closed.

## Standards finding

RFC 9700 §2.4 is normative Best Current Practice and states that the Resource Owner Password Credentials grant **MUST NOT** be used. The reason is structural: the client receives the resource owner's password, expands the credential attack surface, and prevents or complicates modern multi-step and cryptographic authentication.

RFC 10017 §7.3, published in August 2026 for browser-based applications, repeats that ROPC **MUST NOT** be used. For browser applications using OAuth or OpenID Connect, it requires a redirect-based flow such as Authorization Code. A local product decision or accepted-risk note cannot convert a `MUST NOT` mechanism into a conforming implementation.

Therefore the earlier rationale that Direct Access Grants was "the mechanism that actually fits" is superseded. It fits the rendering constraint but violates the protocol/security constraint. This ADR remains Proposed until Keyverse publishes a standards-compliant, versioned headless authentication/session contract that can preserve Naruon's product-owned UI without reintroducing ROPC.

## Current decision

1. **Naruon owns the product surfaces.** Login, signup, recovery, loading, error, permission, responsive, keyboard, and accessibility states are Naruon UI responsibilities.
2. **Keyverse remains identity authority.** Naruon must not copy Keyverse credential rules, user-store semantics, authentication-session state machines, or provider-specific domain truth.
3. **The existing Authorization Code + PKCE federation path remains supported.** The popup variant is an interaction improvement, not a new authentication protocol. The popup is reserved before asynchronous initialization so transient browser user activation is preserved; completion uses a flow-scoped same-origin `BroadcastChannel`, and the authorization page does not retain a live `window.opener` relationship.
4. **Public password routes fail closed.** `POST /auth/password/login` and `POST /auth/password/signup` keep their same-origin rejection boundary but return typed HTTP 503 unavailable responses before parsing or forwarding submitted credentials. An executable regression prevents either route from importing or invoking the password-grant exchange.
5. **A Keyverse replacement is a prerequisite.** The canonical owner must provide and immutably release a headless authentication/session capability suitable for the Naruon-owned surface. Naruon may consume only the released contract through an ACL; an open Keyverse PR or branch head is not a production dependency.
6. **Dormant experimental authority is not accepted architecture.** Password-grant/account-registration helper code retained elsewhere in this Draft is migration evidence only and must be removed before Ready unless it is replaced by the released Keyverse contract. Its mere presence must not make a public password route reachable again.
7. **Secrets remain behind Naruon credential infrastructure.** Runtime application secrets must not become a new `process.env` contract. Environment variables are bootstrap transport only under the repository's `AGENTS.md`; any long-lived Keyverse credential must be retrieved through the protected credential registry/backend boundary after an accepted owner contract exists.

## Security repairs already made in this Draft

These repairs are independently useful and should be preserved where they remain applicable:

- OIDC popup reservation occurs before the first asynchronous login-initialization wait, preserving transient user activation. Popup-blocked browsers fall back to top-level navigation; a failed initialization closes the reserved blank window.
- The authorization popup is opener-severed and result correlation is flow-specific.
- Both public password routes reject foreign or missing Origin/Referer requests before capability evaluation.
- Both public password routes now fail closed before credential-body parsing or any token/account-registration request.
- A route-level policy regression rejects reintroduction of `exchangePasswordForSessionResponse` or `grant_type=password` in the public password endpoints.
- Earlier account-registration transport experiments added stable public error translation, DNS/address pinning, redirect rejection, and response bounds. Those changes are not release evidence and do not justify keeping dormant credential authority; they may be preserved only if a later released Keyverse contract needs equivalent transport controls.

These statements describe source changes in the Draft branch; they are not release claims until exact-head CI, security checks, browser/E2E evidence, review, and protected merge complete.

## Remaining blockers

### Standards-compliant authentication contract

The public password routes no longer execute ROPC; they return HTTP 503 fail-closed responses. The replacement capability itself is still absent. Keyverse must publish an immutable contract that satisfies RFC 9700 and RFC 10017 while allowing the application-owned product surface. The branch must not restore `grant_type=password` while waiting for that contract.

### Buyer-visible password UI state

`SettingsLayout` still renders password login/signup forms and contains copy written for the now-disabled experiment. A user can therefore enter a password into a surface whose server route deliberately returns unavailable, and generic login error handling can misdescribe that condition as bad credentials. Before Ready, the UI must either consume the released replacement contract or present an explicit unavailable/coming-later state that does not solicit credentials. Loading, error, keyboard, responsive, accessibility, and supported locale evidence must follow the final interaction.

### Mutable/unreleased dependency

The companion Keyverse work is open and Keyverse currently has no GitHub Release publication. Its source head cannot be consumed as a canonical production contract. Naruon must not claim signup/login capability landed end-to-end until immutable owner publication evidence exists.

### Dormant password/account-registration authority

The Draft still contains experimental password-grant and account-registration support code outside the now-fail-closed public routes. Before Ready, remove that unused authority and its runtime-secret surface, or replace it atomically with the accepted released owner contract plus executable regression. Dead code is not an acceptable long-term security boundary.

### Successor signup semantics

A future account-creation contract must define idempotency and partial-success/continuation semantics before Naruon wires signup back on. Naruon must not invent a compensating delete across the identity bounded context.

### Authenticated settings refresh

Some Settings data can fail while anonymous. A successful supported login currently refreshes session claims but does not necessarily re-fetch all permission-sensitive settings resources, leaving stale failure state until reload. The authenticated refresh path needs a component-level regression test and causal repair.

### Verification

This Draft still requires current-head unit/type/lint/build evidence, security/SAST/CodeQL evidence, browser E2E for supported login flows and popup-blocked behavior, locale/a11y evidence where material, resolved review threads, and the repository's independent approval/required-check gates. Hosted workflow queuing or startup failure is not GREEN evidence.

## Alternatives

### Keycloak theme

Rejected for the product requirement. It can alter appearance but Keycloak still renders the authentication surface.

### Authorization popup only

Kept for federation. It preserves Naruon's primary tab and can be implemented safely, but the popup still contains authorization-server UI and therefore does not by itself satisfy the requirement for a fully Naruon-rendered local-account surface.

### Direct Access Grants / ROPC

Rejected as the merge architecture. It satisfies the zero-Keycloak-HTML rendering constraint but violates RFC 9700 §2.4 and RFC 10017 §7.3. The public Naruon password routes are now fail-closed rather than treating accepted risk as a standards waiver.

### Naruon reimplementation of Keycloak/WebAuthn internals

Rejected. Reimplementing Keyverse/Keycloak authentication-session or WebAuthn ceremony semantics inside Naruon would duplicate the identity bounded context and create a second security authority. The capability belongs in Keyverse behind a released contract.

## Effects

The desired product boundary remains unchanged: Naruon presents the user experience, while Keyverse owns identity authentication. The experimental password-grant path is no longer executable through Naruon's public password endpoints. Until a released replacement exists, password login/signup are unavailable rather than silently falling back to a prohibited grant.

Any successor must preserve the independent SSO security fixes, consume an immutable Keyverse contract through an ACL, remove obsolete credential authority, align the buyer-visible UI with actual capability, define signup continuation semantics, rehydrate permission-sensitive settings after authentication, and then obtain exact-head evidence before merge.

## References

Lodderstedt, T., Bradley, J., Labunets, A., & Fett, D. (2025). *Best current practice for OAuth 2.0 security* (RFC 9700, BCP 240). RFC Editor. https://doi.org/10.17487/RFC9700

Parecki, A., De Ryck, P., & Waite, D. (2026). *OAuth 2.0 for browser-based applications* (RFC 10017, BCP 212). RFC Editor. https://doi.org/10.17487/RFC10017

Hardt, D. (Ed.). (2012). *The OAuth 2.0 authorization framework* (RFC 6749). RFC Editor. https://doi.org/10.17487/RFC6749

World Wide Web Consortium. (2021). *Web Authentication: An API for accessing Public Key Credentials Level 2*. https://www.w3.org/TR/webauthn-2/
