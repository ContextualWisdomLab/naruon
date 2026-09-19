"""Regression tests for LLM provider error redaction."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import LLMServiceError
from services.llm_service import (
    _log_llm_provider_failure,
    extract_action_items_and_summary,
)


class SecretProviderError(Exception):
    """Provider error whose message represents secret-bearing upstream text."""


def test_llm_provider_failure_log_does_not_render_exception_text(caplog):
    secret = "sk-secret-provider-payload"
    error = SecretProviderError(secret)

    with caplog.at_level(logging.ERROR, logger="services.llm_service"):
        _log_llm_provider_failure("extraction", error)

    assert secret not in caplog.text
    record = caplog.records[-1]
    assert record.getMessage() == "LLM provider request failed"
    assert record.operation == "extraction"
    assert record.error_type == "SecretProviderError"
    assert record.exc_info is None


@pytest.mark.asyncio
async def test_extraction_failure_suppresses_secret_provider_cause(caplog):
    secret = "sk-secret-provider-payload"
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    with (
        patch(
            "services.llm_service.build_llm_provider_http_client",
            new=AsyncMock(return_value=(None, MagicMock())),
        ),
        patch("services.llm_service.AsyncOpenAI", return_value=fake_client),
        patch(
            "services.llm_service.provider_circuit_breaker.call",
            new=AsyncMock(side_effect=SecretProviderError(secret)),
        ),
        caplog.at_level(logging.ERROR, logger="services.llm_service"),
    ):
        with pytest.raises(LLMServiceError) as caught:
            await extract_action_items_and_summary("mail body", "test-api-key")

    assert str(caught.value) == "LLM API error during extraction"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert secret not in caplog.text
    fake_client.close.assert_awaited_once()
