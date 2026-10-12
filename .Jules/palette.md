## 2026-10-12 - Add Loading Spinners to Async Buttons
**Learning:** Buttons with an `aria-busy` state but missing visual loading feedback, such as `<Loader2>`, create a confusing experience where users are unsure if their request is being processed.
**Action:** Always include a visual loading spinner (e.g. `<Loader2 className="animate-spin" />`) inside buttons that trigger asynchronous operations when `aria-busy` is true.
