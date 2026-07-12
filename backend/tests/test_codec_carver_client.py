import httpx
import pytest

from services.codec_carver_client import (
    CodecCarverClient,
    CodecCarverNotConfigured,
    codec_carver_enabled,
)


def test_client_requires_configured_base_url(monkeypatch):
    import core.config as config

    monkeypatch.setattr(config.settings, "CODEC_CARVER_BASE_URL", None, raising=False)
    assert codec_carver_enabled() is False
    with pytest.raises(CodecCarverNotConfigured):
        CodecCarverClient()


@pytest.mark.asyncio
async def test_shrink_media_uploads_and_returns_converted_bytes(monkeypatch):
    import core.config as config

    monkeypatch.setattr(config.settings, "CODEC_CARVER_API_KEY", None, raising=False)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/shrink"
        return httpx.Response(
            200,
            content=b"FLAC-bytes",
            headers={
                "content-type": "audio/flac",
                "content-disposition": 'attachment; filename="meeting.m4a.flac"',
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = CodecCarverClient(base_url="http://codec-carver:8000/", client=http)
        result = await client.shrink_media(
            filename="meeting.m4a", content=b"raw-audio", content_type="audio/mp4"
        )

    assert result.content == b"FLAC-bytes"
    assert result.content_type == "audio/flac"
    assert result.filename == "meeting.m4a.flac"  # from content-disposition
    assert len(seen) == 1
    # multipart upload carried the file + target_bytes
    body = seen[0].content
    assert b'name="file"' in body and b"raw-audio" in body
    assert b'name="target_bytes"' in body


@pytest.mark.asyncio
async def test_shrink_media_sends_api_key_when_configured(monkeypatch):
    import core.config as config
    from pydantic import SecretStr

    monkeypatch.setattr(
        config.settings, "CODEC_CARVER_API_KEY", SecretStr("cc-secret"), raising=False
    )
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, content=b"x", headers={"content-type": "audio/opus"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = CodecCarverClient(base_url="http://codec-carver:8000", client=http)
        await client.shrink_media(filename="a.wav", content=b"y")

    assert captured["authorization"] == "Bearer cc-secret"


@pytest.mark.asyncio
async def test_shrink_media_raises_on_error_status():
    transport = httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "boom"}))
    async with httpx.AsyncClient(transport=transport) as http:
        client = CodecCarverClient(base_url="http://codec-carver:8000", client=http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.shrink_media(filename="a.wav", content=b"y")
