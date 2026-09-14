"""Regression contracts for bounded, explicit deterministic utility tools.

These unit tests deliberately use synthetic strings: they exercise parser and
validation boundaries, not buyer-data acceptance. Tool handlers must reject
ambiguous or malformed requests so the shared execute endpoint can report the
existing ``status=failed`` contract instead of returning a successful payload
that merely contains an error string.
"""

import inspect
import json

import pytest

from api.tools import (
    ExecuteRequest,
    execute_tool,
    hash_generator_handler,
    json_formatter_handler,
    registry,
    url_decoder_handler,
    url_encoder_handler,
)

_UTILITY_TEXT_MAX_CHARS = 100_000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("algorithm", "expected_digest"),
    (
        ("md5", "5d41402abc4b2a76b9719d911017c592"),
        ("sha1", "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"),
        (
            "sha256",
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        ),
        (
            "sha512",
            "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca7"
            "2323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
        ),
    ),
)
async def test_hash_generator_supports_explicit_algorithms(
    algorithm: str,
    expected_digest: str,
) -> None:
    """Each documented algorithm must produce its exact digest without fallback."""

    result = await hash_generator_handler({"text": "hello", "algorithm": algorithm})
    assert result == {"hash": expected_digest}


@pytest.mark.asyncio
async def test_hash_generator_rejects_unknown_algorithm() -> None:
    """A typo must not silently produce a SHA-256 digest under another name."""

    with pytest.raises(ValueError, match="Unsupported hash algorithm"):
        await hash_generator_handler({"text": "hello", "algorithm": "sha25"})


@pytest.mark.asyncio
async def test_execute_tool_reports_unknown_hash_algorithm_as_failed() -> None:
    """The shared execution contract must expose validation failure, not fake success."""

    response = await execute_tool(
        "hash_generator",
        ExecuteRequest(parameters={"text": "hello", "algorithm": "sha25"}),
    )
    assert response.status == "failed"
    assert response.result is None
    assert response.message is not None
    assert "Unsupported hash algorithm" in response.message


@pytest.mark.asyncio
async def test_json_formatter_formats_valid_strict_json() -> None:
    """Valid portable JSON remains losslessly usable after strict parsing."""

    result = await json_formatter_handler({"json_string": '{"a":1,"b":"테스트"}'})
    assert result == {"formatted_json": '{\n  "a": 1,\n  "b": "테스트"\n}'}


@pytest.mark.asyncio
async def test_json_formatter_uses_failed_tool_channel_for_invalid_json() -> None:
    """Malformed JSON must raise so execute_tool returns status=failed."""

    with pytest.raises(ValueError, match="Invalid JSON"):
        await json_formatter_handler({"json_string": '{"missing": }'})

    response = await execute_tool(
        "json_formatter",
        ExecuteRequest(parameters={"json_string": '{"missing": }'}),
    )
    assert response.status == "failed"
    assert response.result is None
    assert response.message is not None
    assert "Invalid JSON" in response.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "json_string",
    (
        '{"role":"member","role":"admin"}',
        '{"score":NaN}',
        '{"score":Infinity}',
        '{"score":-Infinity}',
    ),
)
async def test_json_formatter_rejects_lossy_or_nonportable_json(json_string: str) -> None:
    """Formatting must not discard duplicate values or emit non-standard JSON."""

    with pytest.raises(ValueError, match="Invalid JSON"):
        await json_formatter_handler({"json_string": json_string})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "json_string",
    (
        '{"value":"\\ud800"}',
        '{"\\ud800":"value"}',
        '{"nested":["ok","\\udfff"]}',
    ),
)
async def test_json_formatter_rejects_unpaired_utf16_surrogates(
    json_string: str,
) -> None:
    """Strings that cannot be emitted as UTF-8 JSON must fail before serialization."""

    with pytest.raises(ValueError, match="Invalid JSON"):
        await json_formatter_handler({"json_string": json_string})

    response = await execute_tool(
        "json_formatter",
        ExecuteRequest(parameters={"json_string": json_string}),
    )
    assert response.status == "failed"
    assert response.result is None
    assert response.message is not None
    assert "Invalid JSON" in response.message


@pytest.mark.asyncio
async def test_url_decoder_rejects_malformed_percent_escape() -> None:
    """Malformed percent escapes must not be returned unchanged as successful decode."""

    with pytest.raises(ValueError, match="Invalid URL encoding"):
        await url_decoder_handler({"encoded_url": "order%2Fready%ZZ"})


@pytest.mark.asyncio
@pytest.mark.parametrize("encoded_url", ("%", "%2", "%GG", "100% ready"))
async def test_url_decoder_rejects_every_incomplete_or_nonhex_escape(
    encoded_url: str,
) -> None:
    """Every percent marker must start one complete two-hex-digit escape."""

    with pytest.raises(ValueError, match="Invalid URL encoding"):
        await url_decoder_handler({"encoded_url": encoded_url})


@pytest.mark.asyncio
async def test_url_tools_use_component_semantics_and_round_trip_unicode() -> None:
    """Arbitrary text is one URL component, so structural slashes are encoded too."""

    source = "서울/계약 검토?상태=완료"
    encoded = await url_encoder_handler({"text": source})
    encoded_url = encoded["encoded_url"]
    assert "/" not in encoded_url
    assert encoded_url.startswith("%EC%84%9C%EC%9A%B8%2F")

    decoded = await url_decoder_handler({"encoded_url": encoded_url})
    assert decoded == {"decoded_url": source}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "parameter", "value"),
    (
        (hash_generator_handler, "text", "x" * (_UTILITY_TEXT_MAX_CHARS + 1)),
        (url_encoder_handler, "text", "x" * (_UTILITY_TEXT_MAX_CHARS + 1)),
        (
            url_decoder_handler,
            "encoded_url",
            "x" * (_UTILITY_TEXT_MAX_CHARS + 1),
        ),
        (
            json_formatter_handler,
            "json_string",
            json.dumps({"value": "x" * _UTILITY_TEXT_MAX_CHARS}),
        ),
    ),
)
async def test_utility_tools_reject_oversized_text(handler, parameter, value) -> None:
    """Deterministic local tools still need a bounded CPU/memory input contract."""

    parameters = {parameter: value}
    if handler is hash_generator_handler:
        parameters["algorithm"] = "sha256"

    with pytest.raises(ValueError, match="must not exceed"):
        await handler(parameters)


def test_hash_generator_catalog_copy_is_not_security_misleading() -> None:
    """Weak compatibility digests must not be presented as modern security primitives."""

    tool = registry.get("hash_generator")
    assert tool is not None
    assert tool.category == "유틸리티"
    assert "MD5" in tool.description and "SHA1" in tool.description
    assert "보안" in tool.description


def test_utility_tool_handlers_have_production_docstrings() -> None:
    """Owned production handlers must document their non-obvious contract boundary."""

    handlers = (
        hash_generator_handler,
        url_encoder_handler,
        url_decoder_handler,
        json_formatter_handler,
    )
    assert all(inspect.getdoc(handler) for handler in handlers)
