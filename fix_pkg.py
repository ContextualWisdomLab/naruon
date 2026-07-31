import sys

file_path = "frontend/package.json"
with open(file_path, "r") as f:
    content = f.read()

content = content.replace('"postcss": "^8.5.16",', '"postcss": "^8.5.23",')

with open(file_path, "w") as f:
    f.write(content)

print("Updated frontend/package.json")
