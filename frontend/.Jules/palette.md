## 2026-06-04 - Add loading state to SearchLayout button
**Learning:** Users notice the little things. Missing loading states on async actions makes users unsure if their action registered. Adding a simple loading spinner provides immediate feedback and aligns with accessibility best practices when making dynamic state changes.
**Action:** Always include a visual loading state like `Loader2` for async actions (like the '발신자 관계 캡처' button) to provide immediate feedback to the user.

## 2024-06-07 - Refactoring CalendarLayout buttons
**Learning:** Raw HTML `<button>` elements with complex Tailwind class strings were scattered throughout layout components, which led to inconsistent hover, focus-visible states, and accessibility properties compared to standard design system components.
**Action:** Replace raw HTML `<button>` tags with the `@/components/ui/button` `Button` component using appropriate variants (`ghost`, `outline`) and sizes (`icon-sm`, `sm`) to instantly standardize accessible focus rings and interaction feedback.

## 2026-06-08 - WorkspaceHome unused import investigation
**Learning:** Investigating unused import reports should first verify the current file because the codebase may already have evolved. The repo lint entrypoint is `eslint`, and the focused check for this investigation was `npx eslint src/components/WorkspaceHome.tsx`.
**Action:** Use the focused `npx eslint src/components/WorkspaceHome.tsx` check when confirming WorkspaceHome import health, and reserve broader `eslint` runs for full frontend lint validation.

## 2024-08-02 - CalendarSidebarRight accessibility fix for action buttons
**Learning:** Hardcoded aria-labels like "출시 회의 일정 삭제" inside complex sidebar components cause a poor accessibility experience, as screen readers will announce static text regardless of which actual event was clicked and displayed.
**Action:** Always dynamically interpolate context (such as the event title, e.g. `aria-label={`${selectedDetailEvent?.title ?? '선택한'} 일정 삭제`}`) into ARIA labels for action buttons inside detail views to provide specific, contextual cues for screen reader users.
