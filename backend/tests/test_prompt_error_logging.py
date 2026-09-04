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
    sentinel_secret = "sk-sentinel-must-not-appear"

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
    mock_client.close.assert_awaited_once()
