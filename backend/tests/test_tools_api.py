import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import pytest

from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_SESSION_HMAC_SECRET", secrets.token_urlsafe(48))

from main import app
from api.tools import registry, ToolInfo

def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token() -> str:
    header_segment = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    payload_segment = _base64url_encode(
        json.dumps(
            {
                "ver": 1,
                "iss": "naruon-control-plane",
                "aud": "naruon-api",
                "sub": "alice",
                "role": "member",
                "org": "org-acme",
                "groups": ["group-1"],
                "workspace": "workspace-org-acme",
                "exp": int(time.time()) + 300,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        os.environ["AUTH_SESSION_HMAC_SECRET"].encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def test_tools_rejects_missing_signed_session():
    with TestClient(app) as client:
        response = client.get("/api/tools")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_get_tools_returns_valid_data():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5

    first_tool = data[0]
    assert "code" in first_tool
    assert "name" in first_tool
    assert "description" in first_tool
    assert "category" in first_tool
    assert "is_active" in first_tool
    assert first_tool["category"] == "이메일 분석"


def test_get_tool_success():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools/thread_summarizer",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "thread_summarizer"
    assert data["name"] == "이메일 맥락 요약 (Thread Summarizer)"

def test_get_tool_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools/non_existent_tool",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}


@pytest.mark.asyncio
async def test_execute_tool_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/thread_summarizer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"thread_id": "123"}}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Mock execution successful" in data["result"]
    assert "123" in data["result"]


def test_execute_tool_rejects_unexpected_parameter():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/thread_summarizer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "thread_id": "123",
                    "__proto__": {"polluted": True},
                }
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["message"] == "Tool execution failed"


def test_execute_tool_rejects_invalid_parameter_type():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/thread_summarizer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"thread_id": ["not", "a", "string"]}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["message"] == "Tool execution failed"


def test_execute_tool_not_found():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/non_existent_tool/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {}}
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}

@pytest.mark.asyncio
async def test_execute_tool_inactive():
    try:
        registry.register(
            ToolInfo(
                code="inactive_tool",
                name="Inactive Tool",
                description="This tool is inactive",
                category="Test",
                is_active=False
            ),
            lambda p: "should not run"
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/inactive_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {}}
            )
    finally:
        registry.unregister("inactive_tool")

    assert response.status_code == 400
    assert response.json() == {"detail": "Tool is not active"}

@pytest.mark.asyncio
async def test_execute_tool_handler_error():
    async def error_handler(params):
        raise ValueError("Simulated error")

    try:
        registry.register(
            ToolInfo(
                code="error_tool",
                name="Error Tool",
                description="This tool raises an error",
                category="Test"
            ),
            error_handler
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/error_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {}}
            )
    finally:
        registry.unregister("error_tool")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["message"] == "Tool execution failed"


def test_execute_tool_sync_handler_success():
    try:
        registry.register(
            ToolInfo(
                code="sync_tool",
                name="Sync Tool",
                description="This tool returns synchronously",
                category="Test",
                parameters={"value": "string"},
            ),
            lambda params: {"received": params["value"]},
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/sync_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {"value": "ok"}},
            )
    finally:
        registry.unregister("sync_tool")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"] == {"received": "ok"}
