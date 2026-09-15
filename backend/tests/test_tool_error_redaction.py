import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import httpx

from main import app
from tests.test_tools_api import _signed_session_token

@pytest.mark.asyncio
async def test_webhook_execution_failed_redaction():
    try:
        with patch(
            "api.tools._resolve_global_addresses",
            return_value=("93.184.216.34",),
        ):
            with TestClient(app) as client:
                client.post(
                    "/api/tools",
                    headers={"Authorization": f"Bearer {_signed_session_token()}"},
                    json={
                        "code": "webhook_fail_tool_redaction",
                        "name": "Webhook Fail Tool Redaction",
                        "description": "Calls external webhook",
                        "category": "Test",
                        "parameters": {"input": "string"},
                        "webhook_url": "https://example.com/webhook",
                    },
                )

            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.side_effect = httpx.HTTPError("Simulated HTTP Error")

                with TestClient(app) as client:
                    response = client.post(
                        "/api/tools/webhook_fail_tool_redaction/execute",
                        headers={"Authorization": f"Bearer {_signed_session_token()}"},
                        json={"parameters": {"input": "hello"}},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "failed"
                assert data["message"] == "Webhook execution failed"
                assert "Simulated HTTP Error" not in data["message"]
    finally:
        with TestClient(app) as client:
            client.delete(
                "/api/tools/webhook_fail_tool_redaction",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
            )

@pytest.mark.asyncio
async def test_base64_decoder_invalid_string_redaction():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/base64_decoder/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"encoded_text": "invalid_base64!!"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["message"] == "Invalid Base64 string"
        # Ensure the generic python exception message is not leaked
        assert "Non-base64 digit found" not in data["message"]
