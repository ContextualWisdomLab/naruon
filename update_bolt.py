import re

with open(".jules/bolt.md", "r") as f:
    content = f.read()

content = content.replace("achieving true O(1) performance and memory profile independent of overall map size", "achieving bounded O(min(M, N)) time and O(N) extra memory")
with open(".jules/bolt.md", "w") as f:
    f.write(content)
