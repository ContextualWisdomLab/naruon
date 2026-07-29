## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.
## 2026-07-11 - O(N) Array Mapping Blocked Main Thread in Kanban Board
**Learning:** When long arrays (like tasks sorted into Kanban columns) are mapped inline directly in the React return function, unrelated parent state changes (e.g., search or filter input) trigger full recalculation of the list and React VDOM reconciliation. This blocks the main thread during simple inputs.
**Action:** Use `useMemo` to wrap expensive multi-column mapping operations that render lists of components, using specific dependencies, preventing rendering bottlenecks when other unrelated state variables are updated.

## 2024-05-24 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render.
**Action:** Wrap inline JSX elements that map over arrays (e.g., lists of tasks) in a `useMemo` hook with specific dependencies.

## 2025-03-09 - `dict.setdefault(key, []).append(value)`의 심각한 메모리 할당 오버헤드
**Learning:** 반복문 내에서 `dict.setdefault(key, []).append(value)` 패턴을 사용하여 딕셔너리에 리스트를 생성/초기화하는 것은 매우 비효율적입니다. 이 방식은 키의 존재 여부와 무관하게 매번 루프를 돌 때마다 빈 리스트 `[]` 객체를 새로 메모리에 할당하게 되어, 성능 저하와 메모리 오버헤드를 유발합니다. 백엔드의 데이터 그룹화 로직 등 큰 데이터셋을 처리할 때 이 문제가 특히 두드러집니다.
**Action:** 리스트를 값으로 갖는 딕셔너리를 초기화하고 그룹화할 때는 항상 `collections.defaultdict(list)`를 사용한 후 `dict[key].append(value)`를 호출하여, 불필요한 빈 리스트 메모리 할당 오버헤드를 제거하고 실행 속도를 크게 개선하십시오.
