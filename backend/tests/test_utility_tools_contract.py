import pytest

from api.tools import (
    HASH_GENERATOR_ALGORITHMS,
    UTILITY_TEXT_MAX_CHARS,
    hash_generator_handler,
    json_formatter_handler,
    registry,
    text_reverser_handler,
)


@pytest.mark.asyncio
async def test_hash_generator_exposes_only_portable_cryptographic_algorithms():
    assert HASH_GENERATOR_ALGORITHMS == frozenset({"sha256", "sha384", "sha512"})

    with pytest.raises(ValueError, match="Unsupported hash algorithm"):
        await hash_generator_handler({"text": "hello", "algorithm": "md5"})

    with pytest.raises(ValueError, match="Unsupported hash algorithm"):
        await hash_generator_handler({"text": "hello", "algorithm": "shake_128"})


@pytest.mark.asyncio
async def test_hash_generator_requires_explicit_algorithm():
    with pytest.raises(ValueError, match="Missing required tool parameter"):
        await registry.invoke_tool("hash_generator", {"text": "hello"})


@pytest.mark.asyncio
async def test_hash_generator_rejects_oversized_text():
    with pytest.raises(ValueError, match="Hash input must not exceed"):
        await hash_generator_handler(
            {"text": "x" * (UTILITY_TEXT_MAX_CHARS + 1), "algorithm": "sha256"}
        )


@pytest.mark.asyncio
async def test_json_formatter_rejects_oversized_text():
    with pytest.raises(ValueError, match="JSON input must not exceed"):
        await json_formatter_handler({"raw_json": " " * (UTILITY_TEXT_MAX_CHARS + 1)})


@pytest.mark.asyncio
async def test_json_formatter_formats_only_valid_json():
    result = await json_formatter_handler({"raw_json": '{"b":2,"a":1}'})

    assert result["formatted_json"] == '{\n  "b": 2,\n  "a": 1\n}'

    with pytest.raises(ValueError, match="Invalid JSON string"):
        await json_formatter_handler({"raw_json": "{'not': 'json'}"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_json",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        '{"nested":{"value":NaN}}',
        '{"nested":[1,Infinity,-Infinity]}',
    ],
)
async def test_json_formatter_rejects_nonstandard_numeric_constants(raw_json: str):
    with pytest.raises(ValueError, match="Invalid JSON string"):
        await json_formatter_handler({"raw_json": raw_json})


@pytest.mark.asyncio
async def test_text_reverser_reuses_utility_resource_ceiling():
    result = await text_reverser_handler({"text": "가나다"})
    assert result == {"reversed_text": "다나가"}

    with pytest.raises(ValueError, match="Text reverse input must not exceed"):
        await text_reverser_handler({"text": "x" * (UTILITY_TEXT_MAX_CHARS + 1)})


@pytest.mark.asyncio
async def test_text_reverser_registry_contract_requires_text():
    result = await registry.invoke_tool("text_reverser", {"text": "hello"})
    assert result == {"reversed_text": "olleh"}

    with pytest.raises(ValueError, match="Missing required tool parameter"):
        await registry.invoke_tool("text_reverser", {})
