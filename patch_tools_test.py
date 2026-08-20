with open("backend/tests/test_tools_api.py", "r") as f:
    content = f.read()
content = content.replace("assert response.status_code == 400", "assert response.status_code == 403")
with open("backend/tests/test_tools_api.py", "w") as f:
    f.write(content)
