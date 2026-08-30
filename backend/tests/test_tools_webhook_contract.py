"""Focused regression coverage for tools webhook URL and execution boundaries."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.tools import make_webhook_handler, validate_webhook_url_details


def test_validate_webhook_url_details_accepts_global_https_targets():
    """Resolve a normalized HTTPS target and preserve explicit non-default ports."""
    with patch("api.tools._resolve_global_addresses", return_value=("93.184.216.34",)):
        default_port = validate_webhook_url_details("https://example.com/webhook")
        assert default_port.normalized_url == "https://example.com/webhook"
        assert default_port.hostname == "example.com"
        assert default_port.port == 443
        assert default_port.addresses == ("93.184.216.34",)

        custom_port = validate_webhook_url_details("https://example.com:8443/webhook")
        assert custom_port.normalized_url == "https://example.com:8443/webhook"
        assert custom_port.hostname == "example.com"
        assert custom_port.port == 8443
        assert custom_port.addresses == ("93.184.216.34",)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://example.com/webhook", "Webhook URL must use https"),
        (
            "https://user:pass@example.com/webhook",
            "Webhook URL must not include userinfo",
        ),
        (
            "https://example.com/webhook#fragment",
            "Webhook URL must not include a fragment",
        ),
        ("https:///webhook", "Webhook URL must include a host"),
        (
            "https://example.internal/webhook",
            "Webhook URL host must not use an internal domain suffix",
        ),
    ],
)
def test_validate_webhook_url_details_rejects_unsafe_targets(url: str, message: str):
    """Reject unsafe webhook authorities before any outbound connection is built."""
    with pytest.raises(ValueError, match=message):
        validate_webhook_url_details(url)


@pytest.mark.asyncio
async def test_make_webhook_handler_posts_parameters_to_pinned_client():
    """Execute a validated webhook through the pinned HTTPS client contract."""
    validated = MagicMock(
        normalized_url="https://example.com/webhook",
        hostname="example.com",
        port=443,
        addresses=("93.184.216.34",),
    )
    client = AsyncMock()
    response = MagicMock()
    response.json.return_value = {"success": True}
    client.post.return_value = response
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    with patch("api.tools.validate_webhook_url_details", return_value=validated), patch(
        "api.tools.build_pinned_https_async_client", return_value=client
    ) as build_client:
        handler = make_webhook_handler("https://example.com/webhook")
        result = await handler({"input": "test"})

    assert result == {"success": True}
    build_client.assert_called_with(
        normalized_url="https://example.com/webhook",
        hostname="example.com",
        port=443,
        addresses=("93.184.216.34",),
    )
    client.post.assert_awaited_once_with(
        "https://example.com/webhook",
        json={"parameters": {"input": "test"}},
        timeout=10.0,
    )
    response.raise_for_status.assert_called_once_with()


@pytest.mark.asyncio
async def test_make_webhook_handler_converts_http_errors_to_bounded_contract_error():
    """Convert transport failures into the existing webhook execution error contract."""
    validated = MagicMock(
        normalized_url="https://example.com/webhook",
        hostname="example.com",
        port=443,
        addresses=("93.184.216.34",),
    )
    client = AsyncMock()
    client.post.side_effect = httpx.HTTPError("Simulated HTTP Error")
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    with patch("api.tools.validate_webhook_url_details", return_value=validated), patch(
        "api.tools.build_pinned_https_async_client", return_value=client
    ):
        handler = make_webhook_handler("https://example.com/webhook")
        with pytest.raises(
            ValueError, match="Webhook execution failed: Simulated HTTP Error"
        ):
            await handler({"input": "test"})
