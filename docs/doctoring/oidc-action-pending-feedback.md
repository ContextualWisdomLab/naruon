# OIDC action pending feedback

## Decision

The OIDC sign-in and sign-out controls in `SettingsLayout` own explicit pending state for the network portion of each action. While the corresponding promise is unresolved, the active button is disabled, exposes `aria-busy`, shows the existing `Loader2` spinner, and changes its visible label to `로그인 중` or `로그아웃 중`. Each pending flag is cleared in `finally`, so rejected provider/server requests recover without leaving the control permanently disabled.

This is a bounded interaction-state repair. It does not change the OIDC protocol, browser redirect contract, session cookie semantics, authorization boundary, or provider configuration.

## Problem and evidence

Protected `develop@042b0c70531b229af3acbd0421a2f23098d848b3` had static OIDC action labels. `handleOidcLogin()` can wait on the server login request before navigation, and `handleOidcLogout()` waits while the persisted session is cleared before navigation. During either wait, the corresponding button gave no operation-specific progress feedback and remained eligible for another activation.

The first implementation commit is `eeb0c83455786861d79ec455030c5e66c8dceedc`. The first focused contract commit, `1ff12c590eb432caf4b4a72fc88bcdc24b40d130`, used source-order assertions. That was useful for pinning wiring but weaker than the repository's existing rendered `SettingsLayout` test style because it could pass without proving that React exposed the pending state to an actual button.

The component regression therefore renders `SettingsLayout` in jsdom, uses deferred OIDC promises, and checks the observable DOM state while those promises remain unsettled. It proves that login shows `로그인 중`, native `disabled`, `aria-busy="true"`, and a decorative spinner; a second native `.click()` does not invoke the login action again; resolving the promise restores the control. The logout case proves the same pending semantics and then rejects the provider promise, requiring the button to recover and the existing error surface to contain the provider failure.

`frontend/tests/e2e/settings-oidc-pending-action.spec.ts` adds the real-browser acceptance path without changing production behavior. It uses the existing dashboard API fixture plus an explicit same-origin `/auth/session` route. GET returns a signed authenticated session; DELETE is deliberately held open so the browser must expose `로그아웃 중`, native disabled state, `aria-busy="true"`, and the decorative spinner while exactly one session-clear request is pending. Desktop activates the native control with keyboard Enter; tablet/mobile projects use touch. The test also checks horizontal overflow and records project-specific screenshots. Releasing the held DELETE as HTTP 503 requires the existing alert to surface `OIDC session clear failed`, the signed-in session state to remain visible, and the logout control to recover. This is acceptance source until the exact-head Playwright run and screenshots are terminal; its presence alone is not a GREEN receipt.

## Ownership and rejected alternatives

- #1729 is the current bounded owner for OIDC action pending feedback on the protected `develop` generation.
- #1410 describes essentially the same user intent but is based on an older `develop` generation and currently carries broad unrelated historical drift. Its receipts and unrelated deltas do not transfer here.
- #1453/#1594 own unavailable-action explanation/focusability semantics around Settings controls. This slice must not overwrite that owner when those changes are later reconciled.
- #1241 owns OIDC keyboard focus-indicator styling. Pending feedback does not duplicate that focus contract.
- The generated `.jules/palette.md` addition is removed from the effective delta because the protected file already contains general async-button guidance for `disabled`, `aria-busy`, spinner, and dynamic text. Task-specific repetition is not product authority.

A single shared login/logout mutex was considered but is not introduced without a reproduced cross-action conflict. This slice guarantees duplicate-click prevention for the active action only; it does not claim global serialization of all OIDC transitions.

## Accessibility and UX boundary

The implementation preserves native button semantics and uses `disabled` for the in-flight action rather than adding redundant `aria-disabled`. `aria-busy` communicates that the control is being updated, while the visible label and decorative spinner provide sighted feedback. The spinner remains `aria-hidden` so it does not add a second accessible object.

The Playwright acceptance source now covers native keyboard activation on desktop, touch activation on tablet/mobile, pending-state semantics, responsive overflow, screenshot capture, and failed-session-clear recovery in a real browser. It still does not constitute an assistive-technology or WCAG-conformance receipt until the exact current head executes to terminal success and its artifacts are inspected. Login-side browser pending remains dependent on a configured OIDC provider surface; the component regression retains that bounded contract meanwhile. The new visible strings are also Korean-only because the current protected Settings surface has no released DB-versioned translation-resource contract. KO/EN/JA/ZH/VI/ES/DE/FR delivery therefore remains a product gap rather than being papered over by a browser catalog.

## Delivery gate

- Intent: PASS — progress feedback is tied to the actual awaited OIDC operations.
- Functional completeness: PARTIAL — rendered component regressions cover login/logout pending and cleanup; Playwright acceptance source now covers the logout network wait and error recovery, but exact-current hosted execution is nonterminal.
- Content: PASS for the Korean protected surface; multilingual delivery is unresolved.
- Resilience: PARTIAL — rejection cleanup, desktop keyboard, tablet/mobile touch, responsive overflow, and screenshot paths are encoded; assistive-technology evidence and terminal exact-head browser artifacts are absent.
- Evidence: FAIL for delivery — current-head Playwright/required checks and qualifying independent review are not terminal.
- Distinctiveness: N/A — interaction-state repair, not a visual-identity redesign.

**UI Delivery Gate: FAIL** until the exact integrated candidate has terminal required checks, qualifying independent review, inspected current-head browser artifacts, and the remaining localization/AT prerequisites applicable to final delivery. Do not manufacture evidence with a source-neutral wake commit.

## Traceability

World Wide Web Consortium. (2023). *Accessible Rich Internet Applications (WAI-ARIA) 1.2*. W3C Recommendation, 6 June 2023. https://www.w3.org/TR/wai-aria-1.2/

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines (WCAG) 2.2*. W3C Recommendation (updated 12 December 2024). https://www.w3.org/TR/WCAG22/

Relevant implementation paths: `frontend/src/components/SettingsLayout.tsx`, `frontend/src/components/SettingsLayout.oidc-pending-feedback.test.ts`, `frontend/tests/e2e/settings-oidc-pending-action.spec.ts`, and the existing rendered harness in `frontend/src/components/SettingsLayout.test.tsx`.
