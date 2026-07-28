## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.
## 2026-07-11 - O(N) Array Mapping Blocked Main Thread in Kanban Board
**Learning:** When long arrays (like tasks sorted into Kanban columns) are mapped inline directly in the React return function, unrelated parent state changes (e.g., search or filter input) trigger full recalculation of the list and React VDOM reconciliation. This blocks the main thread during simple inputs.
**Action:** Use `useMemo` to wrap expensive multi-column mapping operations that render lists of components, using specific dependencies, preventing rendering bottlenecks when other unrelated state variables are updated.

## 2024-05-24 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render.
**Action:** Wrap inline JSX elements that map over arrays (e.g., lists of tasks) in a `useMemo` hook with specific dependencies.
## 2025-02-12 - Replaced Memory-Intensive dict.setdefault in Python Loops

**Learning:** 파이썬의 `dict.setdefault(key, []).append(value)` 패턴은 루프 안에서 심각한 메모리 할당 오버헤드를 발생시킵니다. 키가 이미 존재하는지 여부와 상관없이 파이썬 엔진은 매 순회마다 새로운 빈 리스트 객체 `[]`를 생성한 다음, 키가 존재하면 이를 버리기 때문입니다. 성능이 중요한 파이썬 백엔드 코드에서 대량의 데이터를 순회할 때 이 패턴은 눈에 띄는 병목을 유발합니다.
**Action:** 파이썬에서 그룹핑(루프를 돌며 리스트를 딕셔너리에 추가하는 작업)을 수행할 때는 항상 `collections.defaultdict(list)`를 초기화하고 `dict[key].append(value)`를 사용하십시오. 이를 통해 불필요한 객체 생성을 막고 성능을 크게 최적화할 수 있습니다.
