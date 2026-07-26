## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.
## 2026-07-11 - O(N) Array Mapping Blocked Main Thread in Kanban Board
**Learning:** When long arrays (like tasks sorted into Kanban columns) are mapped inline directly in the React return function, unrelated parent state changes (e.g., search or filter input) trigger full recalculation of the list and React VDOM reconciliation. This blocks the main thread during simple inputs.
**Action:** Use `useMemo` to wrap expensive multi-column mapping operations that render lists of components, using specific dependencies, preventing rendering bottlenecks when other unrelated state variables are updated.

## 2024-05-24 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render.
**Action:** Wrap inline JSX elements that map over arrays (e.g., lists of tasks) in a `useMemo` hook with specific dependencies.
## 2025-02-12 - Python `dict.setdefault(..., []).append(...)` 메모리 할당 오버헤드

**Learning:** 파이썬에서 반복문 내에 `dict.setdefault(key, []).append(value)`를 사용하면, 키의 존재 여부와 상관없이 매 반복마다 빈 리스트 `[]`를 새로 메모리에 할당하게 됩니다. 큰 컬렉션이나 성능이 중요한 루프에서 이러한 패턴은 심각한 메모리 할당 오버헤드와 속도 저하를 일으킵니다.

**Action:** 요소를 그룹화하거나 리스트를 초기화할 때 `setdefault(key, [])`를 사용하지 말고, 항상 `collections.defaultdict(list)`를 생성한 후 `dict[key].append(value)`를 사용하여 불필요한 메모리 할당을 방지해야 합니다.
