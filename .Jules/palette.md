## YYYY-MM-DD - Initial
## 2024-08-11 - Dynamic ARIA labels for custom UI components
**Learning:** Hardcoded text within custom complex button UI patterns (like the "제안하기" action in `CalendarCoordinationView`) doesn't properly announce the rich context (like the selected date and attendee availability) to screen readers.
**Action:** Always lift dynamic content states (e.g., specific dates and details within a complex button structure) into a comprehensive `aria-label` attribute on the parent interactive element to ensure proper accessibility.
