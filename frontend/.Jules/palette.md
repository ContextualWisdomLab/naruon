## 2026-06-04 - Add loading state to SearchLayout button
**Learning:** Users notice the little things. Missing loading states on async actions makes users unsure if their action registered. Adding a simple loading spinner provides immediate feedback and aligns with accessibility best practices when making dynamic state changes.
**Action:** Always include a visual loading state like `Loader2` for async actions (like the '발신자 관계 캡처' button) to provide immediate feedback to the user.

## 2024-06-07 - Refactoring CalendarLayout buttons
**Learning:** Raw HTML `<button>` elements with complex Tailwind class strings were scattered throughout layout components, which led to inconsistent hover, focus-visible states, and accessibility properties compared to standard design system components.
**Action:** Replace raw HTML `<button>` tags with the `@/components/ui/button` `Button` component using appropriate variants (`ghost`, `outline`) and sizes (`icon-sm`, `sm`) to instantly standardize accessible focus rings and interaction feedback.

## 2026-06-08 - WorkspaceHome unused import investigation
**Learning:** Investigating unused import reports should first verify the current file because the codebase may already have evolved. The repo lint entrypoint is `eslint`, and the focused check for this investigation was `npx eslint src/components/WorkspaceHome.tsx`.
**Action:** Use the focused `npx eslint src/components/WorkspaceHome.tsx` check when confirming WorkspaceHome import health, and reserve broader `eslint` runs for full frontend lint validation.
## 2026-06-09 - NetworkGraph 버튼 리팩토링
**Learning:** 그래프 시각화 컴포넌트 내의 raw HTML `<button>` 요소들은 일관된 focus-visible 상태와 상호작용 피드백이 부족하여 키보드 탐색 접근성을 떨어뜨립니다.
**Action:** raw HTML `<button>` 태그를 `@/components/ui/button`의 `Button` 컴포넌트로 교체하여 (`outline` 등의 variant와 `sm` 등의 size 사용) 접근성 있는 포커스 링과 상호작용 피드백을 즉시 표준화합니다.
