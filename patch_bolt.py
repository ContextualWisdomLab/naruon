import re

with open(".jules/bolt.md", "r") as f:
    content = f.read()

new_entry = """## 2025-02-12 - Memoizing inline array maps
**Learning:** Inline mapping of arrays inside JSX in large React components causes O(N) recalculation on every render when unrelated parent states change.
**Action:** Wrap inline JSX elements that map over potentially large arrays (e.g., `emails.map`) in a `useMemo` hook with specific dependencies, rather than computing them directly inside the return statement.
"""

if new_entry not in content:
    with open(".jules/bolt.md", "a") as f:
        f.write("\n" + new_entry)

print("Patched.")
