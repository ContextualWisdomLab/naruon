import json

filepath = "frontend/package.json"
with open(filepath, "r") as f:
    data = json.load(f)

if "overrides" in data and "uuid" in data["overrides"]:
    del data["overrides"]["uuid"]

with open(filepath, "w") as f:
    json.dump(data, f, indent=2)

print(f"Patched {filepath}")
