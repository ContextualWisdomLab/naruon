## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.
## 2026-07-11 - O(N) Array Mapping Blocked Main Thread in Kanban Board
**Learning:** When long arrays (like tasks sorted into Kanban columns) are mapped inline directly in the React return function, unrelated parent state changes (e.g., search or filter input) trigger full recalculation of the list and React VDOM reconciliation. This blocks the main thread during simple inputs.
**Action:** Use `useMemo` to wrap expensive multi-column mapping operations that render lists of components, using specific dependencies, preventing rendering bottlenecks when other unrelated state variables are updated.

## 2024-05-24 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render.
**Action:** Wrap inline JSX elements that map over arrays (e.g., lists of tasks) in a `useMemo` hook with specific dependencies.

## 2025-02-12 - dict.setdefault() 대신 collections.defaultdict() 사용으로 불필요한 메모리 할당 제거
**Learning:** 루프 안에서 `dict.setdefault(key, []).append(value)` 패턴을 사용하면, 키의 존재 여부와 무관하게 매번 빈 리스트 `[]`를 새로 생성하므로 성능에 영향을 미칩니다. (수천 개의 데이터 처리시 막대한 가비지 컬렉션 부담 발생)
**Action:** 성능이 중요한 반복문에서는 `collections.defaultdict(list)`를 초기화하고 `dict[key].append(value)` 형태로 사용하여, 루프 내부의 일회성 객체 생성을 없앱니다.
