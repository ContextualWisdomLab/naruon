# Calendar writeback keyboard-focus boundary

## Decision

`CalendarWritebackSection` owns the keyboard-focus affordance for its writeback controls. The create, update, execute, and selectable-source buttons use the same `focus-visible` ring contract so a keyboard user does not lose the active control when moving between actions.

The generated direct-`develop` proposal in #1719 exposed a real asymmetry: update, execute, and source-selection buttons already had the Naruon focus ring, while the create action did not. The generated branch also deleted the existing `.jules/palette.md` history, so it is not the canonical implementation path. The repair stays in #1569, which already owns `CalendarWritebackSection` accessibility semantics.

## RED → fix

- RED `2d6af7294e60da63ce98214930df6dcaed0d3e21` adds a focused regression requiring all three writeback action buttons to retain `focus-visible:outline-none`, `focus-visible:ring-2`, and `focus-visible:ring-ring/40`. The predecessor create button cannot satisfy that contract.
- Fix `bc9fca0716f7e8b2220935ccaf2e85e8ad71be29` adds the missing focus-visible ring to the create action only. No click behavior, disabled state, `aria-busy`, `aria-describedby`, provider execution rule, or source-selection behavior changes.

## Accessibility boundary

WCAG 2.2 Success Criterion 2.4.7 requires keyboard-operable interfaces to provide a visible keyboard-focus indicator. W3C failure technique F78 also warns against suppressing a user-agent outline without supplying an alternative visible focus indicator. Naruon already supplies an author-styled ring on the neighboring writeback controls, so the create action should not be the lone control without the same affordance.

This source repair does **not** by itself prove WCAG 2.2 Success Criterion 2.4.13 Focus Appearance. That criterion additionally depends on rendered indicator area and contrast. The Tailwind token contract and unit regression establish that an authored indicator is present; actual contrast, clipping, focus visibility, responsive layout, and keyboard traversal remain browser-level acceptance work.

## Rejected alternatives

- Keeping #1719 as a second Calendar writeback writer: rejected because #1569 already owns the component accessibility boundary and the generated branch destructively rewrites unrelated `.jules/palette.md` history.
- Removing `outline-none` without an authored replacement: rejected because it would make rendered behavior theme/browser-dependent and could violate the established component focus contract.
- Claiming accessibility completion from class-name assertions: rejected. The regression is source-level evidence only; it does not measure rendered contrast, focus obstruction, or assistive-technology behavior.

## Acceptance

Before #1569 can be considered delivery-complete on a final integrated head:

- the focused unit regression must execute GREEN;
- real-browser keyboard traversal must visibly identify create, update, execute, and writable-source controls;
- the focus indicator must not be clipped or obscured at supported responsive widths;
- rendered focus-ring contrast must be checked against the final theme/background if WCAG 2.4.13 conformance is claimed;
- every then-live required hosted check and qualifying independent review must bind the final exact head and integration context.

## References

World Wide Web Consortium. (2024). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

World Wide Web Consortium, Accessibility Guidelines Working Group. (2026, January 12). *F78: Failure of Success Criterion 1.4.11, 2.4.7 and 2.4.13 due to styling element outlines and borders in a way that removes or renders non-visible the visual focus indicator*. https://www.w3.org/WAI/WCAG22/Techniques/failures/F78.html

World Wide Web Consortium, Accessibility Guidelines Working Group. (2026). *Understanding Success Criterion 2.4.7: Focus Visible*. https://www.w3.org/WAI/WCAG22/Understanding/focus-visible
