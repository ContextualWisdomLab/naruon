## 2024-08-19 - Decorative Icons Accessibility
**Learning:** Purely decorative icons (like Lucide icons) that are used adjacent to descriptive text or within visually grouped blocks should be explicitly hidden from screen readers. Otherwise, screen readers may announce them redundantly, creating a cluttered auditory experience.
**Action:** Always verify that decorative icons (e.g., `<Network>`, `<Shield>`) include `aria-hidden="true"` when they do not convey unique information beyond what is already provided in the accompanying text.
