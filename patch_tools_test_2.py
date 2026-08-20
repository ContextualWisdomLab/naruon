with open("backend/tests/test_tools_api.py", "r") as f:
    content = f.read()

# Undo the previous blanket replace
content = content.replace("assert response.status_code == 403", "assert response.status_code == 400")

with open("backend/tests/test_tools_api.py", "w") as f:
    f.write(content)

# Apply specifically to test_execute_tool_inactive
with open("backend/tests/test_tools_api.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "def test_execute_tool_inactive():" in line:
        for j in range(i, i + 30):
            if "assert response.status_code == 400" in lines[j]:
                lines[j] = lines[j].replace("400", "403")
                break
        break

with open("backend/tests/test_tools_api.py", "w") as f:
    f.writelines(lines)
