import string

import pytest

from api.tools import (
    json_formatter_handler,
    password_generator_handler,
    registry,
    text_statistics_analyzer_handler,
    url_extractor_handler,
)


@pytest.mark.asyncio
async def test_text_statistics_excludes_all_unicode_whitespace():
    result = await text_statistics_analyzer_handler({"text": "A \r\n\t\u00a0B\u0085C"})

    assert result["char_count_no_spaces"] == 3


@pytest.mark.asyncio
async def test_password_generator_guarantees_every_enabled_pool():
    result = await password_generator_handler(
        {
            "length": 32,
            "include_lowercase": True,
            "include_uppercase": True,
            "include_numbers": True,
            "include_symbols": True,
        }
    )
    password = result["password"]

    assert len(password) == 32
    assert any(character in string.ascii_lowercase for character in password)
    assert any(character in string.ascii_uppercase for character in password)
    assert any(character in string.digits for character in password)
    assert any(character in "!@#$%^&*()_+-=[]{}|;:,.<>?" for character in password)


@pytest.mark.asyncio
async def test_password_generator_respects_single_pool_and_safe_fallback():
    digits_only = await password_generator_handler(
        {
            "length": 12,
            "include_lowercase": False,
            "include_uppercase": False,
            "include_numbers": True,
            "include_symbols": False,
        }
    )
    fallback = await password_generator_handler(
        {
            "length": 12,
            "include_lowercase": False,
            "include_uppercase": False,
            "include_numbers": False,
            "include_symbols": False,
        }
    )

    assert len(digits_only["password"]) == 12
    assert all(character in string.digits for character in digits_only["password"])
    assert len(fallback["password"]) == 12
    assert all(
        character in string.ascii_lowercase for character in fallback["password"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
async def test_json_formatter_rejects_nonstandard_constants(constant: str):
    result = await json_formatter_handler({"json_string": f'{{"value": {constant}}}'})

    assert result["is_valid"] is False
    assert result["formatted_json"] is None
    assert result["error"]


@pytest.mark.asyncio
async def test_password_generator_registry_allows_omitted_and_partial_options():
    default_result = await registry.invoke_tool("password_generator", {})
    partial_result = await registry.invoke_tool("password_generator", {"length": 12})

    assert default_result["length"] == 16
    assert len(default_result["password"]) == 16
    assert partial_result["length"] == 12
    assert len(partial_result["password"]) == 12


@pytest.mark.asyncio
async def test_url_extractor_supports_bracketed_ipv6_hosts():
    result = await url_extractor_handler(
        {"text": ("Reach https://[2001:db8::1]/path?q=1 and http://[::1]:8080/health.")}
    )

    assert result == {
        "urls": [
            "https://[2001:db8::1]/path?q=1",
            "http://[::1]:8080/health",
        ],
        "count": 2,
    }
