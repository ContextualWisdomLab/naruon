import json
import sys

filepath = "frontend/package.json"
with open(filepath, "r") as f:
    data = json.load(f)

data["overrides"]["next"] = "^16.2.11"
data["overrides"]["sharp"] = "^0.34.6"
data["overrides"]["postcss"] = "^8.5.23"

with open(filepath, "w") as f:
    json.dump(data, f, indent=2)

print(f"Patched {filepath}")
