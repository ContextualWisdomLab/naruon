import json

filepath = "frontend/package.json"
with open(filepath, "r") as f:
    data = json.load(f)

data["dependencies"]["sharp"] = "^0.35.3"
data["overrides"]["sharp"] = "^0.35.3"

with open(filepath, "w") as f:
    json.dump(data, f, indent=2)

print(f"Patched {filepath}")
