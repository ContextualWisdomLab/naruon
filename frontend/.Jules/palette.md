## 2024-08-24 - Loading states and Lucide mocks
**Learning:** When adding new icons (like `Loader2`) from `lucide-react` for UX improvements, failing to update the `vi.mock("lucide-react", ...)` definitions in the corresponding `.test.tsx` files will instantly crash the Vitest suite with a "No export is defined on the mock" error.
**Action:** Always `grep` the codebase for `vi.mock("lucide-react"` or check related `.test.tsx` files before committing any new `lucide-react` icon usage to ensure test mocks are updated synchronously.
