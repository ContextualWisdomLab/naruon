# Kanban task-card keyboard focus

This note grounds the visible keyboard-focus treatment on task-card buttons in `frontend/src/components/TasksLayout.tsx` and the focused regression in `frontend/src/components/TasksLayout.focus-visible.test.ts`.

## Accessibility boundary

The Kanban cards are native `button` elements and therefore participate in sequential keyboard navigation. WCAG 2.2 Success Criterion 2.4.7 (Focus Visible, Level AA) requires a mode of operation in which keyboard focus is visible. W3C Technique C45 identifies CSS `:focus-visible` as a sufficient technique for providing keyboard-focus indication while allowing user agents to distinguish keyboard focus from ordinary pointer interaction.

The card therefore preserves its existing hover treatment and adds the same explicit keyboard-focus token family already used by other Naruon interactive controls:

- `focus-visible:outline-none`
- `focus-visible:ring-2`
- `focus-visible:ring-ring/40`

The focused source contract locates the Kanban card button from the actual `tasksByStatus[col.id].map((task)` rendering path and requires all three tokens. It does not treat an unrelated focused control elsewhere in `TasksLayout` as evidence for the task card.

## Claim boundary

This bounded change supports the WCAG 2.2 Focus Visible objective for the Kanban task-card control. It does not by itself claim whole-product WCAG 2.2 conformance, Focus Not Obscured conformance, or the Level AAA Focus Appearance area/contrast requirement. Those require rendered-browser assessment across supported themes, zoom levels, forced-colors/high-contrast modes, and viewport states.

## References (APA 7th)

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines (WCAG) 2.2* (W3C Recommendation). https://www.w3.org/TR/WCAG22/

World Wide Web Consortium, Web Accessibility Initiative. (n.d.). *C45: Using CSS `:focus-visible` to provide keyboard focus indication*. Retrieved August 15, 2026, from https://www.w3.org/WAI/WCAG22/Techniques/css/C45

World Wide Web Consortium, Web Accessibility Initiative. (n.d.). *Understanding Success Criterion 2.4.7: Focus Visible*. Retrieved August 15, 2026, from https://www.w3.org/WAI/WCAG22/Understanding/focus-visible

## Verification boundary

The branch is not merge-ready merely because this accessibility treatment, regression, and evidence note exist. Current-head repository CI, required organization workflows, security gates, resolved review threads, and qualifying independent approval remain authoritative.
