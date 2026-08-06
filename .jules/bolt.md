## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.
## 2026-07-11 - O(N) Array Mapping Blocked Main Thread in Kanban Board
**Learning:** When long arrays (like tasks sorted into Kanban columns) are mapped inline directly in the React return function, unrelated parent state changes (e.g., search or filter input) trigger full recalculation of the list and React VDOM reconciliation. This blocks the main thread during simple inputs.
**Action:** Use `useMemo` to wrap expensive multi-column mapping operations that render lists of components, using specific dependencies, preventing rendering bottlenecks when other unrelated state variables are updated.

## 2024-05-24 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render.
**Action:** Wrap inline JSX elements that map over arrays (e.g., lists of tasks) in a `useMemo` hook with specific dependencies.

## 2025-02-12 - Avoided unused setdefault list allocations in grouping loops

**Learning:** `dict.setdefault(key, []).append(value)` evaluates the empty-list default on every iteration, including when the key already exists. In grouping loops, `defaultdict(list)` avoids those transient unused list allocations while preserving insertion order.
**Action:** Use `defaultdict(list)` when missing keys are intentionally initialized with lists. Keep `setdefault` when its eager-default behavior or an ordinary `dict` is part of the required contract, and benchmark before claiming a material end-to-end improvement.
## 2025-02-12 - Rejected Unmeasured useMemo Optimization for Component Arrays

**Learning:** An attempt was made to memoize inline array maps in `CalendarWeekView.tsx` and `CalendarCandidateView.tsx` using `useMemo` to prevent O(N) re-renders. However, this PR was rejected because:
1. Memoizing JSX does not remove React reconciliation generally, retains element trees, and adds dependency bookkeeping overhead.
2. `useMemo` only helps when each array reference remains unchanged across unrelated parent renders, which was not demonstrated.
3. Unmeasured optimizations lacking Profiler traces, interaction latency, or frame evidence are premature.
4. The previous rule to "always memoize mapped JSX" was an unsafe generalization.
**Action:** Never apply `useMemo` to array mapping rendering paths blindly. Always profile the actual components first. If a real bottleneck exists, prefer stabilizing selectors/props, memoizing component boundaries, or virtualizing large ranges over micro-optimizing small component grids. Keep the simpler render path until Profiler evidence dictates otherwise.
