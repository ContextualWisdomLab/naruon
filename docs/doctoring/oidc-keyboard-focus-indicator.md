# OIDC keyboard focus indicator

## Decision

The OIDC sign-in and sign-out buttons in `SettingsLayout` retain an explicit
keyboard-only focus indicator through Tailwind's `focus-visible` variant. The
visual treatment is additive to the existing hover, disabled, border, and
foreground states and does not change authentication, authorization, session,
or OIDC transport behavior.

The current bounded change uses:

```text
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40
```

The default browser outline is removed only while the author-supplied two-pixel
ring is present. A permanent source contract covers both OIDC actions so a later
class refactor cannot silently remove every keyboard-visible indicator.

## Claim boundary

This change supports the WCAG 2.2 Focus Visible objective by ensuring that the
two keyboard-operable OIDC buttons expose an author-supplied visible focus
state. It does not by itself establish whole-product WCAG conformance, Focus
Appearance contrast compliance, focus order, non-obscuration, screen-reader
behavior, or accessibility under every theme and operating-system contrast
mode. Those claims require rendered browser measurements and broader product
assessment.

`focus-visible` is used so the indicator follows keyboard-focus heuristics
without forcing the same visual treatment for ordinary pointer activation. The
button remains a native HTML button and therefore keeps its platform keyboard
semantics.

## Verification and rollback

- `SettingsLayout.oidc-focus.test.ts` reads the production component and requires
  all three focus-indicator tokens on both `OIDC 로그인` and `로그아웃` buttons.
- Repository lint, type checking, tests, production build, accessibility review,
  and current-head security gates remain authoritative.
- Rollback consists of reverting this focused component/test/document set. Do
  not remove the browser outline unless an equivalent or stronger visible focus
  indicator remains.

## References

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines
(WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (2025, September 17). *Understanding Success
Criterion 2.4.7: Focus Visible*. Web Accessibility Initiative.
https://www.w3.org/WAI/WCAG22/Understanding/focus-visible

World Wide Web Consortium. (2026). *Understanding Success Criterion 2.4.13:
Focus Appearance*. Web Accessibility Initiative.
https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html
