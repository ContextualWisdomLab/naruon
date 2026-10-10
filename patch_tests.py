import re

with open("backend/tests/test_tools_api.py", "r") as f:
    content = f.read()

test_code_to_add = r"""
@pytest.mark.asyncio
async def test_hash_generator_tool_sha1():
    result = await registry.invoke_tool(
        "hash_generator", {"text": "hello", "algorithm": "sha1"}
    )
    assert result["hash"] == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"

@pytest.mark.asyncio
async def test_hash_generator_tool_sha256():
    result = await registry.invoke_tool(
        "hash_generator", {"text": "hello", "algorithm": "sha256"}
    )
    assert result["hash"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

@pytest.mark.asyncio
async def test_hash_generator_tool_unsupported():
    with pytest.raises(ValueError, match="Unsupported hash algorithm: unknown"):
        await registry.invoke_tool(
            "hash_generator", {"text": "hello", "algorithm": "unknown"}
        )
"""

if "test_hash_generator_tool_sha1" not in content:
    with open("backend/tests/test_tools_api.py", "a") as f:
        f.write(test_code_to_add)
