# OIDC action pending feedback

## Decision

The OIDC sign-in and sign-out controls in `SettingsLayout` own explicit pending state for the network portion of each action. While the corresponding promise is unresolved, the active button is disabled, exposes `aria-busy`, shows the existing `Loader2` spinner, and changes its visible label to `로그인 중` or `로그아웃 중`. Each pending flag is cleared in `finally`, so rejected provider/server requests recover without leaving the control permanently disabled.

This is a bounded interaction-state repair. It does not change the OIDC protocol, browser redirect contract, session cookie semantics, authorization boundary, or provider configuration.

## Problem and evidence

Protected `develop@042b0c70531b229af3acbd0421a2f23098d848b3` had static OIDC action labels. `handleOidcLogin()` can wait on the server login request before navigation, and `handleOidcLogout()` waits while the persisted session is cleared before navigation. During either wait, the corresponding button gave no operation-specific progress feedback and remained eligible for another activation.

The first implementation commit is `eeb0c83455786861d79ec455030c5e66c8dceedc`. `frontend/src/components/SettingsLayout.oidc-pending-feedback.test.ts` pins the source-order contract for state entry, awaited call, `finally` cleanup, native `disabled`, `aria-busy`, spinner visibility, and pending labels.

The regression is intentionally a focused source contract, not rendered-browser evidence. It prevents the implementation from silently dropping the pending-state wiring while the broader UI evidence lane remains incomplete.

## Ownership and rejected alternatives

- #1729 is the current bounded owner for OIDC action pending feedback on the protected `develop` generation.
- #1410 describes essentially the same user intent but is based on an older `develop` generation and currently carries broad unrelated historical drift. Its receipts and unrelated deltas do not transfer here.
- #1453/#1594 own unavailable-action explanation/focusability semantics around Settings controls. This slice must not overwrite that owner when those changes are later reconciled.
- #1241 owns OIDC keyboard focus-indicator styling. Pending feedback does not duplicate that focus contract.
- The generated `.jules/palette.md` addition is removed from the effective delta because the protected file already contains general async-button guidance for `disabled`, `aria-busy`, spinner, and dynamic text. Task-specific repetition is not product authority.

A single shared login/logout mutex was considered but is not introduced without a reproduced cross-action conflict. This slice guarantees duplicate-click prevention for the active action only; it does not claim global serialization of all OIDC transitions.

## Accessibility and UX boundary

The implementation preserves native button semantics and uses `disabled` for the in-flight action rather than adding redundant `aria-disabled`. `aria-busy` communicates that the control is being updated, while the visible label and decorative spinner provide sighted feedback. The spinner remains `aria-hidden` so it does not add a second accessible object.

This is not a WCAG-conformance claim. Current-head rendered keyboard/screen-reader behavior, focus retention after the button becomes disabled, touch behavior, responsive wrapping, and screenshot evidence still require browser-level verification. The new visible strings are also Korean-only because the current protected Settings surface has no released DB-versioned translation-resource contract. KO/EN/JA/ZH/VI/ES/DE/FR delivery therefore remains a product gap rather than being papered over by a browser catalog.

## Delivery gate

- Intent: PASS — progress feedback is tied to the actual awaited OIDC operations.
- Functional completeness: PARTIAL — focused source regression exists; hosted exact-head checks and rendered interaction evidence are not yet terminal.
- Content: PASS for the Korean protected surface; multilingual delivery is unresolved.
- Resilience: PARTIAL — rejection cleanup is represented in source; keyboard/touch/responsive/error-state browser evidence is absent.
- Evidence: FAIL for delivery — no current-head Storybook/E2E screenshot or assistive-technology receipt yet.
- Distinctiveness: N/A — interaction-state repair, not a visual-identity redesign.

**UI Delivery Gate: FAIL** until the exact integrated candidate has terminal required checks, qualifying independent review, and current-head rendered evidence. Do not manufacture that evidence with a source-neutral wake commit.

## Traceability

World Wide Web Consortium. (2023). *Accessible Rich Internet Applications (WAI-ARIA) 1.2*. W3C Recommendation, 6 June 2023. https://www.w3.org/TR/wai-aria-1.2/

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines (WCAG) 2.2*. W3C Recommendation (updated 12 December 2024). https://www.w3.org/TR/WCAG22/

Relevant implementation paths: `frontend/src/components/SettingsLayout.tsx`, `frontend/src/components/SettingsLayout.oidc-pending-feedback.test.ts`.
