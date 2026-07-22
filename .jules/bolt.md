## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.
## 2026-07-11 - O(N) Array Mapping Blocked Main Thread in Kanban Board
**Learning:** When long arrays (like tasks sorted into Kanban columns) are mapped inline directly in the React return function, unrelated parent state changes (e.g., search or filter input) trigger full recalculation of the list and React VDOM reconciliation. This blocks the main thread during simple inputs.
**Action:** Use `useMemo` to wrap expensive multi-column mapping operations that render lists of components, using specific dependencies, preventing rendering bottlenecks when other unrelated state variables are updated.

## 2024-05-24 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render.
**Action:** Wrap inline JSX elements that map over arrays (e.g., lists of tasks) in a `useMemo` hook with specific dependencies.
## 2024-05-24 - 파이썬 핫 루프(Hot Loop)에서 setdefault 사용 회피
**Learning:** 성능이 중요한 파이썬 루프에서 `dict.setdefault(key, []).append(item)`를 사용하면 키의 존재 여부와 상관없이 *매 반복마다* 기본 인자로 전달할 새로운 빈 리스트 `[]`를 강제로 인스턴스화하게 됩니다. 이는 대규모 데이터셋에 대한 빡빡한 루프에서 심각한 메모리 할당 오버헤드를 유발하고 속도를 저하시킵니다.
**Action:** 키로 항목을 그룹화할 때는 항상 `collections.defaultdict(list)`를 우선적으로 사용하거나, 명시적으로 `if key not in dict:` / `dict[key] = item` 할당을 사용하여 `setdefault`의 지속적이고 암시적인 객체 생성을 건너뛰어야 합니다.
