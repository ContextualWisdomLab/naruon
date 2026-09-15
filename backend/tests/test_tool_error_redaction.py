"""API regressions for public tool failure-detail redaction."""

from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from main import app
from tests.test_tools_api import _signed_session_token


def test_webhook_execution_failed_redaction():
    secret_detail = "Simulated HTTP Error token=do-not-return"
    try:
        with patch(
            "api.tools._resolve_global_addresses",
            return_value=("93.184.216.34",),
        ):
            with TestClient(app) as client:
                create_response = client.post(
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
                assert create_response.status_code == 201

            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.side_effect = httpx.HTTPError(secret_detail)

                with TestClient(app) as client:
                    response = client.post(
                        "/api/tools/webhook_fail_tool_redaction/execute",
                        headers={"Authorization": f"Bearer {_signed_session_token()}"},
                        json={"parameters": {"input": "hello"}},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "failed"
                assert data["result"] is None
                assert data["message"] == "Webhook execution failed"
                assert secret_detail not in data["message"]
    finally:
        with TestClient(app) as client:
            client.delete(
                "/api/tools/webhook_fail_tool_redaction",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
            )


def test_base64_decoder_invalid_string_redaction():
    encoded_text = "invalid_base64!!"
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/base64_decoder/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"encoded_text": encoded_text}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["message"] == "Invalid Base64 string"
    assert encoded_text not in data["message"]
