# Calendar Coordination View Accessibility

`CalendarCoordinationView.tsx` presents numbered meeting proposals with date, time, attendance status, and a visible `제안하기` action label.

## Accessibility problem

A short `aria-label` on the button would replace the descendant-derived accessible name and could omit the date, time, or attendance information needed to distinguish the proposals. Purely visual repetition can also make screen-reader output unnecessarily noisy.

## Implemented pattern

Each button keeps its essential visible text in the accessibility tree and adds a visually hidden contextual prefix such as `<span className="sr-only">1안 제안하기: </span>`. The duplicated visual option badge and trailing action label use `aria-hidden="true"`. The native button role and existing `focus-visible` ring remain intact.

This component pattern aligns with WCAG 2.2 Success Criterion 4.1.2, **Name, Role, Value**, and Success Criterion 2.4.7, **Focus Visible**. This scoped implementation statement does **not** establish conformance of the whole Naruon product.

## Research note

Lazar et al. (2007) studied 100 blind web users and identified confusing screen-reader feedback and poorly designed or unlabeled controls among the leading sources of frustration. The proposal-button pattern therefore preserves task-specific context in the computed accessible name instead of relying on visual grouping alone.

## References

Lazar, J., Allen, A., Kleinman, J., & Malarkey, C. (2007). What frustrates screen reader users on the web: A study of 100 blind users. *International Journal of Human–Computer Interaction, 22*(3), 247–269. https://doi.org/10.1080/10447310709336964

World Wide Web Consortium. (2023a). *Understanding Success Criterion 2.4.7: Focus visible*. https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html

World Wide Web Consortium. (2023b). *Understanding Success Criterion 4.1.2: Name, role, value*. https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html
