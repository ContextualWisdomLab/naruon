"""Security and interoperability contracts for the URL percent-codec tools.

The URL codec is a deterministic text utility, not a URL validator or network
client. These regressions keep it bounded, single-pass, UTF-8 strict, and
separate from the canonical checksum surface owned by the content checksum PR.
"""

from __future__ import annotations

import pytest

from api.tools import registry, url_decoder_handler, url_encoder_handler

URL_CODEC_MAX_INPUT_BYTES = 262_144


def test_hash_generator_is_not_a_parallel_checksum_authority() -> None:
    """Do not expose a second checksum tool with legacy algorithm choices."""

    assert registry.get("hash_generator") is None


@pytest.mark.asyncio
async def test_url_encoder_percent_encodes_component_delimiters_once() -> None:
    """Encode UTF-8 data as one URI-component value with uppercase escapes."""

    result = await url_encoder_handler({"text": "경로/next?x=1%"})

    assert result == {
        "encoded_text": "%EA%B2%BD%EB%A1%9C%2Fnext%3Fx%3D1%25"
    }


@pytest.mark.asyncio
async def test_url_decoder_decodes_exactly_one_percent_encoding_layer() -> None:
    """A percent sign created by decoding is data, never a second escape pass."""

    result = await url_decoder_handler({"text": "%252Fadmin%253Fx%253D1"})

    assert result == {"decoded_text": "%2Fadmin%3Fx%3D1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", ["%", "%2", "%GG", "abc%4Zdef"])
async def test_url_decoder_rejects_malformed_percent_triplets(malformed: str) -> None:
    """RFC 3986 percent escapes must be '%' followed by two hex digits."""

    with pytest.raises(ValueError, match="Malformed percent-encoding"):
        await url_decoder_handler({"text": malformed})


@pytest.mark.asyncio
async def test_url_decoder_rejects_non_utf8_octets() -> None:
    """Decoded octets that are not valid UTF-8 fail closed."""

    with pytest.raises(ValueError, match="Invalid UTF-8 percent-encoding"):
        await url_decoder_handler({"text": "%FF"})


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [url_encoder_handler, url_decoder_handler])
async def test_url_codec_rejects_oversized_utf8_input(handler) -> None:
    """Both directions enforce the same byte-oriented resource boundary."""

    oversized = "가" * ((URL_CODEC_MAX_INPUT_BYTES // 3) + 1)
    with pytest.raises(ValueError, match="URL codec input must not exceed"):
        await handler({"text": oversized})


def test_url_codec_tools_have_one_required_text_parameter() -> None:
    """The catalog contract is deterministic and has no hidden algorithm input."""

    encoder = registry.get("url_encoder")
    decoder = registry.get("url_decoder")

    assert encoder is not None
    assert decoder is not None
    assert encoder.parameters == {"text": "string"}
    assert decoder.parameters == {"text": "string"}
