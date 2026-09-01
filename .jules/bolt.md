## 2024-05-14 - Optimize SearchLayout O(N) Re-renders
**Learning:** `SearchLayout` frequently re-renders due to loading/error states and event handlers. Evaluating `.find()` on a large array of search results during every render loop creates unnecessary O(N) overhead and blocks the main thread.
**Action:** Always wrap `.find()` lookups on state arrays within `useMemo` when they are inside components that handle frequent state changes, to preserve responsiveness.
