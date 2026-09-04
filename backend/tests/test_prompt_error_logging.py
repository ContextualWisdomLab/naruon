import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api import prompts as prompts_module


@pytest.mark.asyncio
async def test_execute_prompt_with_llm_does_not_log_provider_exception_message(
    monkeypatch,
    caplog,
):
    """Provider exception messages must not cross the application log boundary."""
    sentinel_secret = "sentinel-sensitive-value-must-not-appear"

    async def fake_build_llm_provider_http_client(base_url):
        return base_url, MagicMock()

    monkeypatch.setattr(
        prompts_module,
        "build_llm_provider_http_client",
        fake_build_llm_provider_http_client,
    )

    with patch("openai.AsyncOpenAI") as mock_async_openai:
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError(
                f"provider failure Authorization: Bearer {sentinel_secret}"
            )
        )
        mock_async_openai.return_value = mock_client

        with caplog.at_level(logging.ERROR, logger="api.prompts"):
            with pytest.raises(HTTPException) as exc_info:
                await prompts_module.execute_prompt_with_llm(
                    "Summarize this",
                    "provider-api-key",
                    base_url="https://llm-gateway.example.com/v1",
                )

    assert exc_info.value.status_code == 502
    assert "Prompt execution failed" in caplog.text
    assert sentinel_secret not in caplog.text
    assert "Authorization: Bearer" not in caplog.text
    assert caplog.records[-1].error_type == "RuntimeError"
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_replace_or_leak_provider_failure(
    monkeypatch,
    caplog,
):
    """Cleanup errors must preserve the fixed provider response and safe logs."""
    provider_sentinel = "provider-sensitive-value"
    cleanup_sentinel = "cleanup-sensitive-value"

    async def fake_build_llm_provider_http_client(base_url):
        return base_url, MagicMock()

    monkeypatch.setattr(
        prompts_module,
        "build_llm_provider_http_client",
        fake_build_llm_provider_http_client,
    )

    with patch("openai.AsyncOpenAI") as mock_async_openai:
        mock_client = MagicMock()
        mock_client.close = AsyncMock(
            side_effect=RuntimeError(f"cleanup failed {cleanup_sentinel}")
        )
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError(f"provider failed {provider_sentinel}")
        )
        mock_async_openai.return_value = mock_client

        with caplog.at_level(logging.ERROR, logger="api.prompts"):
            with pytest.raises(HTTPException) as exc_info:
                await prompts_module.execute_prompt_with_llm(
                    "Summarize this",
                    "provider-api-key",
                    base_url="https://llm-gateway.example.com/v1",
                )

    assert exc_info.value.status_code == 502
    assert provider_sentinel not in caplog.text
    assert cleanup_sentinel not in caplog.text
    assert [record.error_type for record in caplog.records] == [
        "RuntimeError",
        "RuntimeError",
    ]
    mock_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_http_client_build_failure_uses_safe_boundary(monkeypatch, caplog):
    """HTTP client setup errors must use the same fixed response and safe log."""
    sentinel_secret = "builder-sensitive-value"

    async def fail_build(_base_url):
        raise RuntimeError(f"unsafe URL detail {sentinel_secret}")

    monkeypatch.setattr(
        prompts_module,
        "build_llm_provider_http_client",
        fail_build,
    )

    with caplog.at_level(logging.ERROR, logger="api.prompts"):
        with pytest.raises(HTTPException) as exc_info:
            await prompts_module.execute_prompt_with_llm(
                "Summarize this",
                "provider-api-key",
                base_url="https://llm-gateway.example.com/v1",
            )

    assert exc_info.value.status_code == 502
    assert sentinel_secret not in caplog.text
    assert caplog.records[-1].error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_openai_client_build_failure_closes_safe_http_client(monkeypatch, caplog):
    """OpenAI client construction errors must close the prevalidated HTTP client."""
    sentinel_secret = "constructor-sensitive-value"
    http_client = MagicMock()
    http_client.aclose = AsyncMock()

    async def fake_build(_base_url):
        return "https://llm-gateway.example.com/v1", http_client

    monkeypatch.setattr(
        prompts_module,
        "build_llm_provider_http_client",
        fake_build,
    )

    with patch(
        "openai.AsyncOpenAI",
        side_effect=RuntimeError(f"constructor failed {sentinel_secret}"),
    ):
        with caplog.at_level(logging.ERROR, logger="api.prompts"):
            with pytest.raises(HTTPException) as exc_info:
                await prompts_module.execute_prompt_with_llm(
                    "Summarize this",
                    "provider-api-key",
                    base_url="https://llm-gateway.example.com/v1",
                )

    assert exc_info.value.status_code == 502
    assert sentinel_secret not in caplog.text
    assert caplog.records[-1].error_type == "RuntimeError"
    http_client.aclose.assert_awaited_once()
