"""Client for the Codec Carver audio-conversion service.

naruon proxies recording attachments through Codec Carver to get normalized,
size-bounded FLAC/Opus suitable for STT / omni-modal LLM input. Disabled until
CODEC_CARVER_BASE_URL is configured (``codec_carver_enabled()`` is False).

The current Codec Carver ``POST /shrink`` is synchronous (upload -> converted
file). When its async job API lands, add submit/poll methods alongside
``shrink_media`` without changing this module's callers.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from core.config import settings

CODEC_CARVER_TIMEOUT_SECONDS = 600.0  # audio conversion is slow; generous ceiling
DEFAULT_TARGET_BYTES = 2_000_000_000


class CodecCarverNotConfigured(RuntimeError):
    """Raised when a Codec Carver call is attempted without CODEC_CARVER_BASE_URL."""


@dataclass(frozen=True)
class ConvertedMedia:
    filename: str
    content: bytes
    content_type: str


def codec_carver_base_url() -> str | None:
    raw = settings.CODEC_CARVER_BASE_URL
    return raw.rstrip("/") if raw else None


def codec_carver_enabled() -> bool:
    return codec_carver_base_url() is not None


class CodecCarverClient:
    """Thin async client over Codec Carver's conversion API.

    Pass ``client`` (an ``httpx.AsyncClient``, e.g. on a MockTransport) to inject
    a transport in tests; otherwise a short-lived client is created per call. The
    base URL is operator-configured (an in-cluster Service), so no user-supplied
    URL SSRF allowlisting is needed here.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        resolved = base_url or codec_carver_base_url()
        if not resolved:
            raise CodecCarverNotConfigured("CODEC_CARVER_BASE_URL is not configured")
        self._base_url = resolved.rstrip("/")
        self._client = client

    def _headers(self) -> dict[str, str]:
        api_key = settings.CODEC_CARVER_API_KEY
        if api_key is not None:
            return {"authorization": f"Bearer {api_key.get_secret_value()}"}
        return {}

    async def shrink_media(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        target_bytes: int = DEFAULT_TARGET_BYTES,
    ) -> ConvertedMedia:
        """Upload a recording and return the converted (FLAC/Opus) media bytes."""
        url = f"{self._base_url}/shrink"
        files = {"file": (filename, content, content_type)}
        data = {"target_bytes": str(target_bytes)}

        async def _do(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(
                url,
                files=files,
                data=data,
                headers=self._headers(),
                timeout=CODEC_CARVER_TIMEOUT_SECONDS,
            )

        if self._client is not None:
            response = await _do(self._client)
        else:
            async with httpx.AsyncClient() as client:
                response = await _do(client)
        response.raise_for_status()
        return ConvertedMedia(
            filename=_filename_from_response(response, fallback=filename),
            content=response.content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
        )


def _filename_from_response(response: httpx.Response, *, fallback: str) -> str:
    disposition = response.headers.get("content-disposition", "")
    marker = "filename="
    if marker in disposition:
        name = disposition.split(marker, 1)[1].strip().strip('"')
        if name:
            return name
    return fallback
