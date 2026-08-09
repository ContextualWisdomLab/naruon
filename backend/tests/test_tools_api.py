import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_SESSION_HMAC_SECRET", secrets.token_urlsafe(48))

from api.tools import (
    MAX_TOOL_FAILURE_MESSAGE_CHARS,
    ExecuteRequest,
    ToolInfo,
    ToolRegistry,
    _parameter_type_name,
    _safe_tool_failure_message,
    execute_tool,
    registry,
)
from main import app


REMOVED_CANNED_SOURCE_DERIVED_TOOL_CODES = (
    "thread_summarizer",
    "action_item_extractor",
    "sender_dag_analytics",
    "meeting_candidate_finder",
)


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


def _assert_tool_mutation_not_supported(response) -> None:
    assert response.status_code == 501
    assert response.json() == {
        "detail": {
            "error_code": "tool_mutation_not_supported",
            "message": (
                "Dynamic tool mutations are disabled until tenant-scoped "
                "persistent storage and administrative authorization are "
                "implemented."
            ),
        }
    }


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
    assert len(data) >= 8

    first_tool = data[0]
    assert "code" in first_tool
    assert "name" in first_tool
    assert "description" in first_tool
    assert "category" in first_tool
    assert "is_active" in first_tool


def test_get_retained_tool_success():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools/text_analyzer",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )

    assert response.status_code == 200
    assert response.json()["code"] == "text_analyzer"


@pytest.mark.parametrize("tool_code", REMOVED_CANNED_SOURCE_DERIVED_TOOL_CODES)
def test_startup_catalog_omits_canned_source_derived_tools(tool_code):
    with TestClient(app) as client:
        response = client.get(
            "/api/tools",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )

    assert response.status_code == 200
    assert tool_code not in {tool["code"] for tool in response.json()}


@pytest.mark.parametrize("tool_code", REMOVED_CANNED_SOURCE_DERIVED_TOOL_CODES)
def test_removed_canned_source_derived_tool_detail_returns_not_found(tool_code):
    with TestClient(app) as client:
        response = client.get(
            f"/api/tools/{tool_code}",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}


@pytest.mark.parametrize("tool_code", REMOVED_CANNED_SOURCE_DERIVED_TOOL_CODES)
def test_removed_canned_source_derived_tool_execute_returns_not_found(tool_code):
    with TestClient(app) as client:
        response = client.post(
            f"/api/tools/{tool_code}/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {}},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}


def test_get_tool_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools/non_existent_tool",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}


def test_startup_catalog_omits_unsupported_spam_phishing_detector():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )

    assert response.status_code == 200
    assert "spam_phishing_detector" not in {
        tool["code"] for tool in response.json()
    }


def test_removed_spam_phishing_detector_detail_returns_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/tools/spam_phishing_detector",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}


def test_removed_spam_phishing_detector_execute_returns_not_found():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/spam_phishing_detector/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "email_content": "Urgent: update your bank password now",
                    "sender_domain": "secure-bank-login.ru",
                }
            },
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tool not found"}


@pytest.mark.parametrize(
    "tool_code", ["email_categorizer", "meeting_agenda_generator"]
)
def test_registry_omits_lexical_pseudo_topic_tools(tool_code):
    assert registry.get(tool_code) is None


def test_keyword_extractor_is_disclosed_as_lexical_term_frequency():
    tool = registry.get("keyword_extractor")
    assert tool is not None
    assert tool.description == (
        "텍스트 본문에서 빈도와 최초 출현 순으로 반복 용어를 추출합니다."
    )


@pytest.mark.asyncio
async def test_execute_tone_analyzer():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/tone_analyzer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "draft_content": "Give me the file.",
                    "recipient_relationship": "manager",
                }
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "manager" in data["result"]["refined_draft"]
    assert "Give me the file." in data["result"]["refined_draft"]
    assert "suggestions" in data["result"]
    assert data["result"]["tone_score"] == 85


def test_execute_tool_rejects_unexpected_parameter():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/text_analyzer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "text": "123",
                    "__proto__": {"polluted": True},
                }
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert "Unexpected tool parameter" in data["message"]


def test_execute_tool_rejects_invalid_parameter_type():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/text_analyzer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": ["not", "a", "string"]}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert "Invalid tool parameter type" in data["message"]


def test_execute_tool_rejects_missing_required_parameter():
    try:
        registry.register(
            ToolInfo(
                code="req_tool",
                name="Required Tool",
                description="Test tool",
                category="Test",
                parameters={"req_param": "string"},
            ),
            lambda p: "ok",
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/req_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {}},
            )
    finally:
        registry.unregister("req_tool")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "Missing required tool parameter" in data["message"]


def test_execute_tool_no_parameters_accepted():
    try:
        registry.register(
            ToolInfo(
                code="no_param_tool",
                name="No Param Tool",
                description="Test tool",
                category="Test",
                parameters=None,
            ),
            lambda p: "ok",
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/no_param_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {"unexpected": "value"}},
            )
    finally:
        registry.unregister("no_param_tool")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "Tool does not accept parameters" in data["message"]


def test_execute_tool_not_a_dict_parameter():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/text_analyzer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": "not_a_dict"},  # type: ignore
        )

    assert response.status_code == 422


def test_execute_tool_not_found():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/non_existent_tool/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {}},
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
                is_active=False,
            ),
            lambda p: "should not run",
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/inactive_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {}},
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
                category="Test",
            ),
            error_handler,
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/tools/error_tool/execute",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"parameters": {}},
            )
    finally:
        registry.unregister("error_tool")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert "Simulated error" in data["message"]


@pytest.mark.asyncio
async def test_execute_tool_failure_log_does_not_include_user_controlled_lines(caplog):
    hostile_code = "error_tool\r\nforged_event=true"

    def error_handler(_params):
        raise ValueError("failure\r\nforged_exception=true")

    try:
        registry.register(
            ToolInfo(
                code=hostile_code,
                name="Error Tool",
                description="This tool raises an error",
                category="Test",
            ),
            error_handler,
        )
        with caplog.at_level("WARNING", logger="api.tools"):
            response = await execute_tool(
                hostile_code,
                ExecuteRequest(parameters={}),
            )
    finally:
        registry.unregister(hostile_code)

    assert response.status == "failed"
    records = [
        record for record in caplog.records if record.message == "tool_execution_failed"
    ]
    assert len(records) == 1
    assert records[0].exception_type == "ValueError"
    assert len(records[0].exception_traceback_fingerprint) == 12
    int(records[0].exception_traceback_fingerprint, 16)
    assert records[0].tool_code_fingerprint == hashlib.sha256(
        hostile_code.encode("utf-8")
    ).hexdigest()[:12]
    assert response.message == r"failure\r\nforged_exception=true"
    assert "\r" not in response.message
    assert "\n" not in response.message
    assert hostile_code not in caplog.text
    assert "forged_exception" not in caplog.text


def test_safe_tool_failure_message_escapes_controls_and_bounds_output():
    message = _safe_tool_failure_message(
        ValueError("\t\x01" + ("x" * MAX_TOOL_FAILURE_MESSAGE_CHARS))
    )

    assert message.startswith(r"\t\u0001")
    assert len(message) == MAX_TOOL_FAILURE_MESSAGE_CHARS
    assert "\t" not in message
    assert "\x01" not in message


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


def test_registry_no_handler():
    r = ToolRegistry()
    r._tools["orphan"] = ToolInfo(
        code="orphan", name="O", description="D", category="C"
    )
    with pytest.raises(ValueError, match="No handler registered for tool orphan"):
        import asyncio

        asyncio.run(r.invoke_tool("orphan", {}))


def test_validate_parameters_no_schema_but_params_provided():
    r = ToolRegistry()
    r._tools["no_params"] = ToolInfo(
        code="no_params", name="N", description="D", category="C"
    )
    with pytest.raises(ValueError, match="Tool does not accept parameters"):
        r._validate_parameters("no_params", {"some": "param"})


def test_validate_parameters_missing_required():
    r = ToolRegistry()
    r._tools["req_params"] = ToolInfo(
        code="req_params",
        name="N",
        description="D",
        category="C",
        parameters={"req1": "string"},
    )
    with pytest.raises(ValueError, match="Missing required tool parameter"):
        r._validate_parameters("req_params", {})


def test_parameter_type_name_dict():
    assert _parameter_type_name({"type": "integer"}) == "integer"
    assert _parameter_type_name({"other": "thing"}) == "string"
    assert _parameter_type_name(123) == "string"


@pytest.mark.asyncio
async def test_text_analyzer_tool_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/text_analyzer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "Hello world\nThis is a test "}},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    result = data["result"]
    assert result["char_count"] == 27
    assert result["char_count_no_spaces"] == 21
    assert result["word_count"] == 6


@pytest.mark.asyncio
async def test_base64_encoder_tool_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/base64_encoder/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "hello"}},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    result = data["result"]
    assert result["encoded_text"] == "aGVsbG8="


@pytest.mark.asyncio
async def test_base64_decoder_tool_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/base64_decoder/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"encoded_text": "aGVsbG8="}},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    result = data["result"]
    assert result["decoded_text"] == "hello"


@pytest.mark.asyncio
async def test_base64_decoder_tool_invalid_input():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/base64_decoder/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"encoded_text": "invalid_base64_string!"}},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert "Invalid Base64 string" in data["message"]


def test_create_tool_mutation_fails_closed_without_registry_write():
    code = "new_custom_tool"
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/tools",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={
                    "code": code,
                    "name": "Custom Tool",
                    "description": "Custom Description",
                    "category": "Custom Category",
                    "parameters": {"param1": "string"},
                    "is_active": True,
                },
            )
        _assert_tool_mutation_not_supported(response)
        assert registry.get(code) is None
    finally:
        registry.unregister(code)


def test_create_tool_mutation_fails_closed_even_with_safe_webhook():
    code = "webhook_custom_tool"
    try:
        with patch("api.tools._resolve_global_addresses") as resolve_addresses:
            with TestClient(app) as client:
                response = client.post(
                    "/api/tools",
                    headers={"Authorization": f"Bearer {_signed_session_token()}"},
                    json={
                        "code": code,
                        "name": "Webhook Tool",
                        "description": "Calls an external webhook",
                        "category": "Custom Category",
                        "parameters": {"input": "string"},
                        "webhook_url": "https://example.com/webhook",
                    },
                )

        _assert_tool_mutation_not_supported(response)
        assert registry.get(code) is None
        resolve_addresses.assert_not_called()
    finally:
        registry.unregister(code)


def test_update_tool_mutation_fails_closed_without_registry_change():
    code = "update_tool"

    def handler(_params):
        return "ok"

    original = ToolInfo(
        code=code,
        name="Old Name",
        description="Old Desc",
        category="Test",
    )
    original_snapshot = original.model_copy(deep=True)
    try:
        registry.register(original, handler)

        with TestClient(app) as client:
            response = client.patch(
                f"/api/tools/{code}",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
                json={"name": "New Name", "is_active": False},
            )

        _assert_tool_mutation_not_supported(response)
        assert registry.get(code) == original_snapshot
        assert registry._handlers[code] is handler
    finally:
        registry.unregister(code)


def test_delete_tool_mutation_fails_closed_without_registry_change():
    code = "delete_tool"

    def handler(_params):
        return "ok"

    original = ToolInfo(
        code=code,
        name="Do Not Delete",
        description="Do Not Delete",
        category="Test",
    )
    try:
        registry.register(original, handler)

        with TestClient(app) as client:
            response = client.delete(
                f"/api/tools/{code}",
                headers={"Authorization": f"Bearer {_signed_session_token()}"},
            )

        _assert_tool_mutation_not_supported(response)
        assert registry.get(code) == original
        assert registry._handlers[code] is handler
    finally:
        registry.unregister(code)


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/api/tools",
            {
                "code": "unauthorized_tool",
                "name": "Unauthorized Tool",
                "description": "Must not be registered",
                "category": "Test",
            },
        ),
        ("PATCH", "/api/tools/text_analyzer", {"name": "Unauthorized"}),
        ("DELETE", "/api/tools/text_analyzer", None),
    ],
)
def test_tool_mutation_routes_require_signed_session(method, path, payload):
    with TestClient(app) as client:
        response = client.request(method, path, json=payload)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/tools"),
        ("PATCH", "/api/tools/non_existent_tool"),
    ],
)
def test_tool_mutation_tombstones_do_not_validate_request_models(method, path):
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            headers={
                "Authorization": f"Bearer {_signed_session_token()}",
                "Content-Type": "application/json",
            },
            content="{not-json",
        )

    _assert_tool_mutation_not_supported(response)


def test_tool_mutation_routes_are_hidden_from_openapi():
    from api.tools import router as tools_router

    schema_app = FastAPI()
    schema_app.include_router(tools_router)
    paths = schema_app.openapi()["paths"]

    assert "post" not in paths["/api/tools"]
    assert "patch" not in paths["/api/tools/{code}"]
    assert "delete" not in paths["/api/tools/{code}"]


@pytest.mark.asyncio
async def test_webhook_handler_success():
    from api.tools import make_webhook_handler

    with patch(
        "api.tools._resolve_global_addresses",
        return_value=("93.184.216.34",),
    ):
        handler = make_webhook_handler("https://example.com/webhook")
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"webhook_success": True}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            result = await handler({"input": "hello"})

    assert result == {"webhook_success": True}
    mock_post.assert_awaited_once_with(
        "https://example.com/webhook",
        json={"parameters": {"input": "hello"}},
        timeout=10.0,
    )


@pytest.mark.asyncio
async def test_webhook_handler_http_error():
    from api.tools import make_webhook_handler

    with patch(
        "api.tools._resolve_global_addresses",
        return_value=("93.184.216.34",),
    ):
        handler = make_webhook_handler("https://example.com/webhook")
        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.HTTPError("Simulated HTTP Error"),
        ):
            with pytest.raises(
                ValueError,
                match="Webhook execution failed: Simulated HTTP Error",
            ):
                await handler({"input": "hello"})


def test_tool_registry_execute_no_handler():
    # Internal registry test for branch coverage
    registry._tools["no_handler_tool"] = ToolInfo(
        code="no_handler_tool",
        name="No Handler",
        description="No handler",
        category="Test",
    )
    try:
        with pytest.raises(ValueError, match="No handler registered for tool"):
            import asyncio

            asyncio.run(registry.invoke_tool("no_handler_tool", {}))
    finally:
        registry._tools.pop("no_handler_tool", None)


def test_parameter_matches_type():
    from api.tools import _parameter_matches_type, _parameter_type_name

    assert _parameter_matches_type(123, "number") is True
    assert _parameter_matches_type(123.4, "number") is True
    assert _parameter_matches_type(True, "number") is False

    assert _parameter_matches_type(123, "integer") is True
    assert _parameter_matches_type(123.4, "integer") is False
    assert _parameter_matches_type(True, "integer") is False

    assert _parameter_matches_type(True, "boolean") is True
    assert _parameter_matches_type("true", "boolean") is False

    assert _parameter_matches_type([], "array") is True
    assert _parameter_matches_type({}, "object") is True
    assert (
        _parameter_matches_type("test", "unknown") is True
    )  # default to string validator

    assert _parameter_type_name({"type": "integer"}) == "integer"
    assert _parameter_type_name({"other": "value"}) == "string"
    assert _parameter_type_name(123) == "string"


def test_registry_execute_sync():
    # Test internal method for full coverage of sync branch
    import asyncio

    registry.register(
        ToolInfo(
            code="internal_sync",
            name="internal_sync",
            description="Sync",
            category="Test",
        ),
        lambda p: "internal_sync_result",
    )
    try:
        res = asyncio.run(registry.invoke_tool("internal_sync", {}))
        assert res == "internal_sync_result"
    finally:
        registry.unregister("internal_sync")


def test_validate_parameters_not_dict():
    # Internal registry test to hit line 80
    with pytest.raises(ValueError, match="Tool parameters must be an object"):
        registry._validate_parameters("some_code", "not a dict")  # type: ignore


def test_is_safe_webhook_url_coverage():
    from api.tools import is_safe_webhook_url

    with patch(
        "api.tools._resolve_global_addresses",
        return_value=("93.184.216.34",),
    ):
        assert is_safe_webhook_url("https://example.com/webhook") is True
    assert is_safe_webhook_url("ftp://example.com") is False
    assert is_safe_webhook_url("http://example.com") is False
    assert is_safe_webhook_url("https://example.internal") is False
    assert is_safe_webhook_url("https://localhost/admin") is False
    assert is_safe_webhook_url("https://127.0.0.1/admin") is False
    assert is_safe_webhook_url("https://[::1]/admin") is False
    assert is_safe_webhook_url("https://user:pass@example.com/webhook") is False
    assert is_safe_webhook_url("https://example.com/webhook#fragment") is False


def test_execute_email_translator():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/email_translator/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "text": "Hello, thank you for the meeting.",
                    "target_language": "ko",
                }
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "안녕하세요" in data["result"]["translated_text"]
    assert "감사합니다" in data["result"]["translated_text"]
    assert "회의" in data["result"]["translated_text"]
    assert data["result"]["source_language_detected"] == "en"


def test_execute_reply_drafter():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/reply_drafter/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "original_email": "Can we meet tomorrow at 2pm?",
                    "intent": "긍정적 동의",
                }
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "긍정적 동의" in data["result"]["draft"]
    assert "tomorrow at 2pm" in data["result"]["draft"]


def test_execute_sentiment_analyzer():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/sentiment_analyzer/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "I am disappointed about this urgent issue."}},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"]["sentiment"] == "negative"
    assert data["result"]["score"] < 0.5
    assert "불만" in data["result"]["key_emotions"]


def test_execute_grammar_checker():
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/grammar_checker/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={
                "parameters": {
                    "draft_content": "안녕 하세요. 확인 부탁 드립니다. 감사 합니다."
                }
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "안녕하세요" in data["result"]["corrected_text"]
    assert "확인 부탁드립니다" in data["result"]["corrected_text"]
    assert "감사합니다" in data["result"]["corrected_text"]
    assert data["result"]["errors_found"] == 3


def test_validate_webhook_url_no_host():
    from api.tools import validate_webhook_url

    with pytest.raises(ValueError, match="Webhook URL must include a host"):
        validate_webhook_url("https://")


def test_validate_webhook_url_invalid_port():
    from api.tools import validate_webhook_url

    with pytest.raises(ValueError, match="Webhook URL port must be valid"):
        validate_webhook_url("https://example.com:9999999/webhook")


def test_detect_text_language_en():
    from api.tools import _detect_text_language

    assert _detect_text_language("English text") == "en"


def test_detect_text_language_unknown():
    from api.tools import _detect_text_language

    assert _detect_text_language("1234") == "unknown"


@pytest.mark.asyncio
async def test_sentiment_analyzer_handler_positive_and_neutral():
    from api.tools import sentiment_analyzer_handler

    result = await sentiment_analyzer_handler({"text": "thank you"})
    assert result["sentiment"] == "positive"

    result = await sentiment_analyzer_handler({"text": "hello"})
    assert result["sentiment"] == "neutral"


@pytest.mark.asyncio
async def test_analysis_handlers_safe_and_fallthrough_paths():
    from api.tools import (
        email_translator_handler,
        grammar_checker_handler,
        sentiment_analyzer_handler,
    )

    untranslated = await email_translator_handler(
        {"text": "Hello, thank you for the meeting.", "target_language": "en"}
    )
    assert untranslated["translated_text"] == "Hello, thank you for the meeting."
    assert untranslated["source_language_detected"] == "en"

    nonurgent_negative = await sentiment_analyzer_handler(
        {"text": "I am disappointed."}
    )
    assert nonurgent_negative["sentiment"] == "negative"
    assert nonurgent_negative["key_emotions"] == ["불만", "우려"]

    clean_draft = await grammar_checker_handler(
        {"draft_content": "안녕하세요. 확인 부탁드립니다. 감사합니다."}
    )
    assert clean_draft["errors_found"] == 0
    assert clean_draft["suggestions"] == []


def test_detect_text_language_ko():
    from api.tools import _detect_text_language

    assert _detect_text_language("안녕하세요") == "ko"


@pytest.mark.asyncio
async def test_keyword_extractor_handler():
    from api.tools import keyword_extractor_handler

    text = "Important, project! Project billing; important schedule."
    first = await keyword_extractor_handler({"text": text})
    second = await keyword_extractor_handler({"text": text})

    assert first == second
    assert first == {
        "keywords": ["important", "project", "billing", "schedule"],
        "keyword_count": 4,
    }

    korean = await keyword_extractor_handler(
        {"text": "프로젝트 일정 검토와 프로젝트 예산 검토가 필요합니다."}
    )
    assert korean["keywords"][:3] == ["프로젝트", "일정", "검토와"]

    empty = await keyword_extractor_handler({"text": "the and 123"})
    assert empty == {"keywords": [], "keyword_count": 0}


def test_execute_analysis_tool_rejects_oversized_text():
    from api.tools import ANALYSIS_TEXT_MAX_CHARS

    with TestClient(app) as client:
        response = client.post(
            "/api/tools/keyword_extractor/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "x" * (ANALYSIS_TEXT_MAX_CHARS + 1)}},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "result": None,
        "message": (
            f"Analysis text must not exceed {ANALYSIS_TEXT_MAX_CHARS} characters"
        ),
    }
