## 2025-02-12 - Eliminated O(N log N) Final Sort in Backend Email Fetching

**Learning:** The database query inside `get_emails` (`backend/api/emails.py`) already returns rows sorted chronologically descending (`order_by(Email.date.desc())`). Previously, this array was manually reversed, grouped by thread with a dictionary, and then the dictionary values were sorted again into descending order. Because Python 3.7+ preserves dictionary insertion order, iterating the descending query results and inserting elements into a group dictionary inherently guarantees that the dict's values are strictly ordered by the *newest message in each thread*. This eliminates the need for both the `O(N)` list reversal and the costly `O(N log N)` `sorted()` final step when assembling threads.

**Action:** Whenever iterating pre-sorted array lists from the database to group them into unique threads or items, leverage Python's dictionary insertion order preservation guarantees instead of explicitly appending arrays and sorting them. The first item encountered sets the insertion order, and if the parent array is already sorted descending, the resulting grouped entries are mathematically guaranteed to be correctly ordered.

## 2025-02-20 - Deduplication Optimization
**Learning:** Python's `dict.fromkeys()` leverages the underlying C implementation and insertion-order preservation (in Python 3.7+) to deduplicate elements while maintaining order. It can be faster in some workloads (particularly when list size isn't massive) than manually tracking a `set` and appending to a `list` inside a `for` loop, especially for list preparations before database queries or API calls.
**Action:** Use `list(dict.fromkeys(iterable))` instead of `seen = set(); result = []` for order-preserving deduplication loops to improve CPU performance.

## 2025-02-21 - Optimize list comprehensions over dictionary defaults
**Learning:** Using `.get(key, [])` inside a frequently called function forces Python to allocate a new empty list object in memory every time the key is missing, increasing garbage collection overhead.
**Action:** When iterating over a dictionary value in performance-sensitive code, use `if key in my_dict:` to avoid instantiating default objects like `[]` or `set()` when the key is absent.
