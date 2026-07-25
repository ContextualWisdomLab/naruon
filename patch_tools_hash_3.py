import os

filepath = "backend/api/tools.py"
with open(filepath, "r") as f:
    content = f.read()

# I patched the wrong location. I need to make sure hashlib.md5 is patched properly.
# The error was: Use of weak MD5 hash for security. Consider usedforsecurity=False
# and: Use of weak SHA1 hash for security. Consider usedforsecurity=False

content = content.replace(
    'hashlib.md5(encoded).hexdigest()',
    'hashlib.md5(encoded, usedforsecurity=False).hexdigest()'
)
content = content.replace(
    'hashlib.sha1(encoded).hexdigest()',
    'hashlib.sha1(encoded, usedforsecurity=False).hexdigest()'
)

with open(filepath, "w") as f:
    f.write(content)

print("Hashlib patched.")
