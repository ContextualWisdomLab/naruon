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
## 2025-02-12 - Prevented O(N) re-renders in "My Tasks" list
**Learning:** Similar to the Kanban board, inline mapping of the "My Tasks" list (`filteredTicketTasks.map`) inside `TasksLayout.tsx` causes unnecessary O(N) recalculations and VDOM reconciliations on every render when unrelated state variables change, potentially blocking the main thread.
**Action:** Always extract and wrap inline array mappings of complex UI components inside JSX with `useMemo`, ensuring they only recalculate when their specific dependencies (like the source array or relevant state) change.
