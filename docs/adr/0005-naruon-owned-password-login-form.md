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

## Research traceability

The prohibition above comes from the current normative RFCs; the academic literature is supporting evidence rather than a substitute for those requirements. Fett, Küsters, and Schmitz (2016) formally analyze OAuth 2.0—including the authorization-code and resource-owner-password modes—in an expressive web model and show that authentication/session-integrity guarantees depend on following the protocol's security recommendations and applying the required fixes. That result supports treating protocol security guidance as part of the system model rather than as an optional deployment note.

Bonneau et al. (2012) evaluate web-authentication schemes across security, usability, and deployability rather than security in isolation. Naruon's successor acceptance therefore includes both protocol correctness and buyer-visible behavior: the product must not solicit credentials for a capability that is deliberately unavailable, and a future Keyverse contract must be evaluated for usable recovery, multi-step authentication, deployment boundaries, and migration—not only whether an API call succeeds.

## Current decision

1. **Naruon owns the product surfaces.** Login, signup, recovery, loading, error, permission, responsive, keyboard, and accessibility states are Naruon UI responsibilities.
2. **Keyverse remains identity authority.** Naruon must not copy Keyverse credential rules, user-store semantics, authentication-session state machines, or provider-specific domain truth.
3. **The existing Authorization Code + PKCE federation path remains supported.** The popup variant is an interaction improvement, not a new authentication protocol. The popup is reserved before asynchronous initialization so transient browser user activation is preserved; completion uses a flow-scoped same-origin `BroadcastChannel`, and the authorization page does not retain a live `window.opener` relationship.
4. **Public password routes fail closed.** `POST /auth/password/login` and `POST /auth/password/signup` keep their same-origin rejection boundary but return typed HTTP 503 unavailable responses before parsing or forwarding submitted credentials. An executable regression prevents either route from importing or invoking password-grant authority.
5. **A Keyverse replacement is a prerequisite.** The canonical owner must provide and immutably release a headless authentication/session capability suitable for the Naruon-owned surface. Naruon may consume only the released contract through an ACL; an open Keyverse PR or branch head is not a production dependency.
6. **Dormant experimental credential authority is removed.** The Draft no longer retains `exchangePasswordForSessionResponse`, its `grant_type=password` implementation, or the Naruon-local password-registration client and bearer-token configuration. An executable regression protects this absence while the owner capability is unavailable.
7. **Secrets remain behind Naruon credential infrastructure.** Runtime application secrets must not become a new `process.env` contract. Environment variables are bootstrap transport only under the repository's `AGENTS.md`; any future long-lived Keyverse credential must be retrieved through the protected credential registry/backend boundary after an accepted owner contract exists.

## Security repairs already made in this Draft

These repairs are independently useful and should be preserved where they remain applicable:

- OIDC popup reservation occurs before the first asynchronous login-initialization wait, preserving transient user activation. Popup-blocked browsers fall back to top-level navigation; a failed initialization closes the reserved blank window.
- The authorization popup is opener-severed and result correlation is flow-specific.
- Both public password routes reject foreign or missing Origin/Referer requests before capability evaluation.
- Both public password routes fail closed before credential-body parsing or any token/account-registration request.
- The public-route authority regression rejects reintroduction of `exchangePasswordForSessionResponse` or `grant_type=password`.
- The same regression rejects dormant password-grant code in the shared OIDC module and rejects a Naruon-local password-registration client while the immutable Keyverse replacement is unavailable.
- The ADR index records this decision as `Proposed` / `BLOCKED-UPSTREAM` rather than claiming end-to-end password login or signup.

These statements describe source changes in the Draft branch; they are not release claims until exact-head CI, security checks, browser/E2E evidence, review, and protected merge complete.

## Remaining blockers

### Standards-compliant authentication contract

The public password routes no longer execute ROPC; they return HTTP 503 fail-closed responses. The replacement capability itself is still absent. Keyverse must publish an immutable contract that satisfies RFC 9700 and RFC 10017 while allowing the application-owned product surface. The branch must not restore `grant_type=password` while waiting for that contract.

### Buyer-visible password UI state

`SettingsLayout` still renders password login/signup forms and contains copy written for the disabled experiment. A user can therefore enter a password into a surface whose server route deliberately returns unavailable, and generic login error handling can misdescribe that condition as bad credentials. Before Ready, the UI must either consume the released replacement contract or present an explicit unavailable state that does not solicit credentials. Loading, error, keyboard, responsive, accessibility, and supported locale evidence must follow the final interaction.

### Mutable/unreleased dependency

The companion Keyverse work is open and Keyverse currently has no GitHub Release publication. Its source head cannot be consumed as a canonical production contract. Naruon must not claim signup/login capability landed end-to-end until immutable owner publication evidence exists.

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

Rejected as the merge architecture. It satisfies the zero-Keycloak-HTML rendering constraint but violates RFC 9700 §2.4 and RFC 10017 §7.3. The public Naruon password routes are fail-closed, and the dormant ROPC implementation has been removed rather than treated as an accepted exception.

### Naruon reimplementation of Keycloak/WebAuthn internals

Rejected. Reimplementing Keyverse/Keycloak authentication-session or WebAuthn ceremony semantics inside Naruon would duplicate the identity bounded context and create a second security authority. The capability belongs in Keyverse behind a released contract.

## Effects

The desired product boundary remains unchanged: Naruon presents the user experience, while Keyverse owns identity authentication. The experimental password-grant path is not executable through Naruon's public password endpoints and its Naruon-local exchange/registration authority is no longer retained. Until a released replacement exists, password login/signup are unavailable rather than silently falling back to a prohibited grant.

Any successor must preserve the independent SSO security fixes, consume an immutable Keyverse contract through an ACL, align the buyer-visible UI with actual capability, define signup continuation semantics, rehydrate permission-sensitive settings after authentication, and then obtain exact-head evidence before merge.

## References

Bonneau, J., Herley, C., van Oorschot, P. C., & Stajano, F. (2012). The quest to replace passwords: A framework for comparative evaluation of web authentication schemes. In *2012 IEEE Symposium on Security and Privacy* (pp. 553–567). IEEE. https://doi.org/10.1109/SP.2012.44

Fett, D., Küsters, R., & Schmitz, G. (2016). A comprehensive formal security analysis of OAuth 2.0. In *Proceedings of the 2016 ACM SIGSAC Conference on Computer and Communications Security* (pp. 1204–1215). Association for Computing Machinery. https://doi.org/10.1145/2976749.2978385

Lodderstedt, T., Bradley, J., Labunets, A., & Fett, D. (2025). *Best current practice for OAuth 2.0 security* (RFC 9700, BCP 240). RFC Editor. https://doi.org/10.17487/RFC9700

Parecki, A., De Ryck, P., & Waite, D. (2026). *OAuth 2.0 for browser-based applications* (RFC 10017, BCP 212). RFC Editor. https://doi.org/10.17487/RFC10017

Hardt, D. (Ed.). (2012). *The OAuth 2.0 authorization framework* (RFC 6749). RFC Editor. https://doi.org/10.17487/RFC6749

World Wide Web Consortium. (2021). *Web Authentication: An API for accessing Public Key Credentials Level 2*. https://www.w3.org/TR/webauthn-2/
