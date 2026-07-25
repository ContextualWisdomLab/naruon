import os

filepath = "backend/api/tools.py"
with open(filepath, "r") as f:
    content = f.read()

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
