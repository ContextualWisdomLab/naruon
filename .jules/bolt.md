## 2024-05-24 - Array manipulation in useMemo hooks
**Learning:** Chaining array methods like `.map().filter().slice(0, 5)` or `Array.from(map.values()).slice(0, 5).map()` in React `useMemo` hooks creates full O(N) intermediate arrays before slicing, which blocks the main thread and uses excessive memory on large datasets (like NetworkGraph nodes/edges).
**Action:** Replace map/filter/slice chains with early-breaking `for...of` loops to bound execution time and memory overhead to O(1) when a constant size limit exists.
