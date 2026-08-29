## 2025-05-24 - NetworkGraph O(N) array creation bounds
**Learning:** Using `Array.from(map.values()).slice(0, N)` creates an array of the entire map in memory (O(N) operations) before truncating it. This can block the main thread and consume significant memory for large datasets in React components when we only need a few items.
**Action:** Replace `Array.from(iterable).slice(0, N)` with a bounded `for...of` loop that breaks early when the desired number of items is reached, keeping the complexity O(1).
