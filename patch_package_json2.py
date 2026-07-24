import json

filepath = "frontend/package.json"
with open(filepath, "r") as f:
    data = json.load(f)

data["dependencies"]["next"] = "^16.2.11"
data["dependencies"]["postcss"] = "^8.5.23"
data["dependencies"]["sharp"] = "^0.34.6"
data["devDependencies"]["postcss"] = "^8.5.23"

with open(filepath, "w") as f:
    json.dump(data, f, indent=2)

print(f"Patched {filepath}")
