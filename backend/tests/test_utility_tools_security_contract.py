"""Security and interoperability contracts for deterministic utility tools.

The utility catalog must not create a parallel legacy checksum authority, and
text codecs must fail closed on malformed, type-confused, or oversized input.
JSON formatting accepts strict RFC 8259-style data only and never silently
collapses duplicate object members.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from api.tools import (
    json_formatter_handler,
    registry,
    url_decoder_handler,
    url_encoder_handler,
)

URL_CODEC_MAX_INPUT_BYTES = 262_144
JSON_FORMATTER_MAX_INPUT_BYTES = 1_048_576


def test_hash_generator_is_not_a_parallel_checksum_authority() -> None:
    """Keep checksums in the bounded modern-algorithm checksum surface."""

    assert registry.get("hash_generator") is None


@pytest.mark.asyncio
async def test_url_encoder_percent_encodes_one_uri_component() -> None:
    """Encode component delimiters and preserve UTF-8 deterministically."""

    result = await url_encoder_handler({"text": "경로/next?x=1%"})

    assert result == {"encoded_text": "%EA%B2%BD%EB%A1%9C%2Fnext%3Fx%3D1%25"}


@pytest.mark.asyncio
async def test_url_decoder_decodes_exactly_one_layer() -> None:
    """A decoded percent sign remains data rather than a second escape pass."""

    result = await url_decoder_handler({"text": "%252Fadmin%253Fx%253D1"})

    assert result == {"decoded_text": "%2Fadmin%3Fx%3D1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", ["%", "%2", "%GG", "abc%4Zdef"])
async def test_url_decoder_rejects_malformed_percent_triplets(malformed: str) -> None:
    """Reject any percent sign that is not followed by two hexadecimal digits."""

    with pytest.raises(ValueError, match="Malformed percent-encoding"):
        await url_decoder_handler({"text": malformed})


@pytest.mark.asyncio
async def test_url_decoder_rejects_non_utf8_octets() -> None:
    """Reject percent-decoded octets that are not valid UTF-8."""

    with pytest.raises(ValueError, match="Invalid UTF-8 percent-encoding"):
        await url_decoder_handler({"text": "%FF"})


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [url_encoder_handler, url_decoder_handler])
@pytest.mark.parametrize("invalid_text", [None, 17, b"bytes", ["text"]])
async def test_url_codec_rejects_non_string_input(
    handler: Callable[[dict[str, Any]], Any],
    invalid_text: object,
) -> None:
    """Reject type-confused payloads with one stable public error contract."""

    with pytest.raises(ValueError, match="URL codec text must be a string"):
        await handler({"text": invalid_text})


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [url_encoder_handler, url_decoder_handler])
async def test_url_codec_rejects_oversized_utf8_input(
    handler: Callable[[dict[str, Any]], Any],
) -> None:
    """Bound both codec directions by encoded UTF-8 byte size."""

    oversized = "가" * ((URL_CODEC_MAX_INPUT_BYTES // 3) + 1)
    with pytest.raises(ValueError, match="URL codec input must not exceed"):
        await handler({"text": oversized})


def test_url_codec_registry_uses_one_required_text_parameter() -> None:
    """Expose one symmetric text-in contract without hidden algorithm inputs."""

    encoder = registry.get("url_encoder")
    decoder = registry.get("url_decoder")

    assert encoder is not None
    assert decoder is not None
    assert encoder.parameters == {"text": "string"}
    assert decoder.parameters == {"text": "string"}


@pytest.mark.asyncio
async def test_json_formatter_rejects_duplicate_object_members() -> None:
    """Do not silently apply last-key-wins semantics to ambiguous JSON."""

    with pytest.raises(ValueError, match="Duplicate JSON object member"):
        await json_formatter_handler({"json_string": '{"role":"user","role":"admin"}'})


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_value", [None, 17, b"{}", {"key": "value"}])
async def test_json_formatter_rejects_non_string_input(invalid_value: object) -> None:
    """Reject non-text JSON input before parser-specific exceptions escape."""

    with pytest.raises(ValueError, match="JSON formatter input must be a string"):
        await json_formatter_handler({"json_string": invalid_value})


@pytest.mark.asyncio
async def test_json_formatter_rejects_oversized_utf8_input() -> None:
    """Bound parser work before loading an attacker-controlled JSON document."""

    oversized = '"' + ("가" * ((JSON_FORMATTER_MAX_INPUT_BYTES // 3) + 1)) + '"'
    with pytest.raises(ValueError, match="JSON formatter input must not exceed"):
        await json_formatter_handler({"json_string": oversized})
