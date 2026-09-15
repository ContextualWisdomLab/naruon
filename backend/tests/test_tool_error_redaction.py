"""Regression tests for public tool failure-detail redaction."""

import httpx
import pytest

from api import tools


class _FailingWebhookClient:
    """Minimal async client that exposes a transport detail only through its exception."""

    def __init__(self, detail: str):
        self._detail = detail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.HTTPError(self._detail)


@pytest.mark.asyncio
async def test_webhook_failure_response_does_not_expose_transport_detail(monkeypatch):
    secret_detail = "provider detail: token=do-not-return"
    monkeypatch.setattr(
        tools,
        "_resolve_global_addresses",
        lambda *args, **kwargs: ("93.184.216.34",),
    )
    monkeypatch.setattr(
        tools,
        "build_pinned_https_async_client",
        lambda **kwargs: _FailingWebhookClient(secret_detail),
    )

    tool_code = "webhook_error_redaction_contract"
    handler = tools.make_webhook_handler("https://example.com/webhook")
    tools.registry.register(
        tools.ToolInfo(
            code=tool_code,
            name="Webhook error redaction contract",
            description="Test-only webhook failure contract",
            category="Test",
            parameters={"input": "string"},
        ),
        handler,
    )
    try:
        response = await tools.execute_tool(
            tool_code,
            tools.ExecuteRequest(parameters={"input": "hello"}),
        )
    finally:
        tools.registry.unregister(tool_code)

    assert response.status == "failed"
    assert response.result is None
    assert response.message == "Webhook execution failed"
    assert secret_detail not in response.message


@pytest.mark.asyncio
async def test_base64_failure_response_does_not_expose_decoder_detail(monkeypatch):
    secret_detail = "decoder detail: source=/srv/private/input"

    def _raise_decoder_error(*args, **kwargs):
        raise ValueError(secret_detail)

    monkeypatch.setattr(tools.base64, "b64decode", _raise_decoder_error)

    response = await tools.execute_tool(
        "base64_decoder",
        tools.ExecuteRequest(parameters={"encoded_text": "YQ=="}),
    )

    assert response.status == "failed"
    assert response.result is None
    assert response.message == "Invalid Base64 string"
    assert secret_detail not in response.message
