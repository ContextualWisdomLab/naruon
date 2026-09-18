# Settings native-disabled accessibility decision

Date: 2026-09-17
Owner lane: `SettingsLayout` native disabled semantics (#1676)

## Problem

Two Settings actions already use native HTML `<button disabled>` while an asynchronous operation is in progress. The same buttons also carried `aria-disabled`, duplicating the host-language disabled state. The product needs one authoritative disabled-state mechanism without losing the separate operation-status signal.

## Decision

For native `<button>` elements that are actually inoperable during the operation:

- use the HTML `disabled` attribute as the disabled-state authority;
- retain `aria-busy` to expose the independent in-progress state;
- do not add `aria-disabled` when `disabled` is present.

This applies to the account-settings save action and the runner registration-token rotation action in `frontend/src/components/SettingsLayout.tsx`.

The decision is intentionally narrow. `aria-disabled` remains appropriate for widgets that cannot use a native host-language disabled mechanism or when a design intentionally keeps an otherwise disabled command discoverable/focusable. This change does not create a repository-wide ban on `aria-disabled`.

## Standards traceability

The WHATWG HTML Standard defines `disabled` as the native boolean disabled-state mechanism for supported form controls and requires disabled controls to suppress user-interaction click dispatch. ARIA in HTML advises authors to use the HTML `disabled` attribute where it is available and specifically says authors should not use `aria-disabled="true"` on an element that also has `disabled`. WAI-ARIA separately defines `aria-disabled` as a perceivable-but-inoperable state and `aria-busy` as a distinct state, so retaining `aria-busy` does not duplicate the native disabled semantic.

### References (APA 7th)

WHATWG. (2026). *HTML Standard: Enabling and disabling form controls—The disabled attribute*. https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#enabling-and-disabling-form-controls-the-disabled-attribute

World Wide Web Consortium. (2026). *ARIA in HTML*. https://www.w3.org/TR/html-aria/

World Wide Web Consortium. (2026). *Accessible Rich Internet Applications (WAI-ARIA) 1.3*. https://www.w3.org/TR/wai-aria-1.3/

## Code and test linkage

Current source contract:

- `frontend/src/components/SettingsLayout.tsx`
- `frontend/src/components/SettingsLayout.native-disabled.test.tsx`

The focused regression must continue to assert, for both owned buttons, that native `disabled` and operation-state `aria-busy` remain present while redundant `aria-disabled` is absent. The regression is a source-contract guard; it is not browser accessibility evidence.

## Rejected alternatives

1. Keep both `disabled` and `aria-disabled`.
   Rejected because it duplicates the disabled state and conflicts with current ARIA-in-HTML author guidance.
2. Remove native `disabled` and keep only `aria-disabled`.
   Rejected because ARIA does not provide native button inoperability; scripting would have to reproduce interaction suppression and focus behavior already supplied by HTML.
3. Remove `aria-busy` together with `aria-disabled`.
   Rejected because busy/in-progress state is not the same semantic as disabled/inoperable state.

## Verification boundary

Source intent and deterministic regression are present in #1676. Browser/keyboard/responsive accessibility verification remains a separate delivery gate and must not be inferred from this document or from source-level tests. A source-neutral commit or bot acknowledgement is not executable evidence and must not be counted as review, CI, browser, or accessibility proof.
