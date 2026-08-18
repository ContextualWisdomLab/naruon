# Calendar unavailable-action discoverability

## Status

`ACTIVE_PR` — this record applies to the bounded `CalendarSidebarRight` accessibility repair and must not be represented as protected-`develop` behavior until the PR integrates.

## Buyer problem

Native `disabled` removes a button from sequential keyboard focus. The predecessor Palette implementation compensated by moving focus to anonymous wrapper `div` elements and putting the explanation in `title`. That makes the wrapper rather than the action the discovery target and leaves the prerequisite explanation dependent on a pointer-oriented advisory mechanism.

The calendar sidebar needs to answer two questions at the action itself:

1. Is this action currently available?
2. If not, what should the customer do next?

## Decision

- Keep each unavailable action as the native design-system `Button` in the sequential focus order.
- Express the unavailable state with `aria-disabled="true"` rather than the HTML `disabled` attribute when discoverability is useful.
- Suppress unavailable activation at the button event boundary; `aria-disabled` communicates state but does not itself prevent behavior.
- Associate each unavailable button with visible next-action guidance through `aria-describedby`.
- Avoid extra focusable wrapper elements and do not rely on `title` as the explanation contract.
- Preserve the shared `Button` component and its runtime design tokens rather than adding a calendar-specific button style system.

For location, the visible recovery instruction is: `일정에 위치를 추가하면 위치를 열 수 있습니다.`

For selection-dependent actions, the visible recovery instruction is: `왼쪽 캘린더에서 일정을 선택하면 삭제·복사·수정할 수 있습니다.`

## Standards boundary

WAI-ARIA 1.2 defines `aria-disabled` as a programmatic unavailable-state signal; unlike the host-language `disabled` attribute it does not automatically suppress focus or functionality, so authors retain responsibility for preventing activation. The WAI-ARIA Authoring Practices Guide further notes that keeping an unavailable control focusable can be useful when discoverability matters. That APG guidance is non-normative product guidance, while the ARIA state semantics are normative.

WCAG 2.2 Success Criterion 2.4.3 requires focus order to preserve meaning and operability. Its current Understanding document specifically warns against focus patterns that make a control appear to receive focus multiple times through nested focusable elements. This slice therefore keeps one focus target per action.

This bounded repair does not claim whole-product WCAG conformance, assistive-technology interoperability across every browser, or that the currently placeholder calendar actions have acquired new mutation authority.

## Verification contract

`frontend/src/components/calendar/CalendarSidebarRight.unavailable-actions.test.ts` fails if the component returns to native `disabled`, focusable explanation wrappers, missing visible recovery copy, missing `aria-disabled`, or missing `aria-describedby` relationships.

Current-head repository CI, frontend typecheck/test/coverage/build, security/SAST, central coverage/review, zero valid unresolved findings, and qualifying independent approval remain merge requirements.

## Rollback

A rollback may restore the prior visual layout, but it must not restore anonymous focusable wrappers or remove a usable programmatic/visible explanation path. If future product actions become executable, their handlers must preserve the same fail-closed `aria-disabled` activation guard.

## References — APA 7th

World Wide Web Consortium. (2023). *Accessible Rich Internet Applications (WAI-ARIA) 1.2*. https://www.w3.org/TR/wai-aria-1.2/

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium, Web Accessibility Initiative. (n.d.). *Developing a keyboard interface*. Retrieved August 18, 2026, from https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/

World Wide Web Consortium, Web Accessibility Initiative. (n.d.). *Understanding Success Criterion 2.4.3: Focus order*. Retrieved August 18, 2026, from https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html
