## 2025-02-23 - [O(N) Array Allocation during Map Slice]
**Learning:** Avoid using chained operations like `Array.from(map.values()).slice(0, N)` in React components (`useMemo`) because it allocates intermediate O(N) arrays, which creates garbage collection pressure and CPU overhead when dealing with large datasets (e.g. large graphs in `NetworkGraph.tsx`).
**Action:** Use an early-exit `for...of` loop with a `break` condition to only allocate and iterate over the exact N elements required.
