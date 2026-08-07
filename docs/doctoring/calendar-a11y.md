# Calendar Coordination View Accessibility

In `CalendarCoordinationView.tsx`, the proposal buttons were initially designed with visual content representing numbered options (e.g., "1안"), date/time, attendance status, and a generic action text ("제안하기").

**Accessibility Problem:**
Using an `aria-label` directly on the `<button>` element completely overrides its accessible name, discarding all the descendant text content that might be crucial for context. If we used `aria-label="1안 제안하기"`, a screen reader user would miss the date, time, and attendance status.

**Solution:**
Instead of `aria-label`, we use a visually hidden element (`<span className="sr-only">1안 제안하기: </span>`) inside the button structure alongside the visible text. Furthermore, we add `aria-hidden="true"` to purely decorative or redundant visual elements (like the visible "1안" badge and the generic "제안하기" label).

This ensures the computed accessible name sequentially combines the `sr-only` context and the essential visible date and attendance information, conforming with Web Content Accessibility Guidelines (WCAG) 2.2 for accessible names and focus indicators (buttons retain `focus-visible` styles).

Reference: W3C Web Accessibility Initiative. (2023). Web Content Accessibility Guidelines (WCAG) 2.2. W3C.
