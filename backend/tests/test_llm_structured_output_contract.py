"""OpenAI-compatible structured-output contracts used by Naruon consumers."""

import json

import httpx
import pytest
from openai import AsyncOpenAI
from openai.lib._parsing import type_to_response_format_param
from pydantic import ValidationError

from core.exceptions import LLMServiceError
from services.llm_service import ExtractionResult, extract_action_items_and_summary
from services.project_graph import llm_extractor
from services.project_graph.llm_extractor import ExtractionPayload
from services import rag_service
from services.rag_service import GroundedAnswerPayload


class _CaptureTransport(httpx.AsyncBaseTransport):
    def __init__(self, content: str) -> None:
        self.body = None
        self.content = content

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.body = json.loads(request.content)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "chatcmpl-contract",
                "object": "chat.completion",
                "created": 0,
                "model": "orchestrator/free",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": self.content},
                        "finish_reason": "stop",
                    }
                ],
            },
        )


@pytest.mark.parametrize(
    ("payload_model", "valid_payload"),
    [
        (ExtractionResult, {"summary": "s", "action_items": []}),
        (ExtractionPayload, {"objects": [], "relations": []}),
        (GroundedAnswerPayload, {"answer": "a", "cited_email_ids": []}),
    ],
)
def test_structured_payloads_use_strict_json_schema_and_reject_extra_fields(
    payload_model,
    valid_payload,
):
    envelope = type_to_response_format_param(payload_model)

    assert envelope["type"] == "json_schema"
    assert envelope["json_schema"]["strict"] is True
    assert envelope["json_schema"]["schema"]["additionalProperties"] is False
    with pytest.raises(ValidationError):
        payload_model.model_validate({**valid_payload, "unexpected_field": True})


@pytest.mark.asyncio
async def test_summary_uses_real_sdk_json_schema_on_orchestrator_route(monkeypatch):
    transport = _CaptureTransport(
        json.dumps({"summary": "s", "action_items": [], "confidence": 90})
    )
    client = AsyncOpenAI(
        api_key="test-token",
        base_url="https://orchestrator.example/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr("services.llm_service.AsyncOpenAI", lambda **_: client)
    monkeypatch.setattr(
        "services.llm_service.build_llm_provider_http_client",
        _validated_client,
    )

    result = await extract_action_items_and_summary(
        "email",
        "tenant-scoped-token",
        base_url="https://orchestrator.example/v1",
        model="orchestrator/free",
    )

    assert result.summary == "s"
    assert transport.body["model"] == "orchestrator/free"
    assert transport.body["response_format"]["type"] == "json_schema"
    assert transport.body["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_project_graph_uses_real_sdk_json_schema_on_orchestrator_route(
    monkeypatch,
):
    transport = _CaptureTransport(json.dumps({"objects": [], "relations": []}))
    client = AsyncOpenAI(
        api_key="test-token",
        base_url="https://orchestrator.example/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(llm_extractor, "AsyncOpenAI", lambda **_: client)
    monkeypatch.setattr(
        llm_extractor, "build_llm_provider_http_client", _validated_client
    )

    result = await llm_extractor._call_llm(
        api_key="tenant-scoped-token",
        base_url="https://orchestrator.example/v1",
        model="orchestrator/free",
        segments_json='{"segments": []}',
    )

    assert result.objects == []
    assert transport.body["model"] == "orchestrator/free"
    assert transport.body["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_grounded_answer_uses_real_sdk_json_schema_on_orchestrator_route(
    monkeypatch,
):
    transport = _CaptureTransport(
        json.dumps({"answer": "grounded", "cited_email_ids": []})
    )
    client = AsyncOpenAI(
        api_key="test-token",
        base_url="https://orchestrator.example/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(rag_service, "AsyncOpenAI", lambda **_: client)
    monkeypatch.setattr(
        rag_service, "build_llm_provider_http_client", _validated_client
    )

    result = await rag_service._call_llm(
        api_key="tenant-scoped-token",
        base_url="https://orchestrator.example/v1",
        model="orchestrator/free",
        question="q",
        emails_json='{"emails": []}',
    )

    assert result.answer == "grounded"
    assert transport.body["model"] == "orchestrator/free"
    assert transport.body["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_schema_extra_field_fails_closed(monkeypatch):
    transport = _CaptureTransport(
        json.dumps({"summary": "s", "action_items": [], "unexpected": True})
    )
    client = AsyncOpenAI(
        api_key="test-token",
        base_url="https://orchestrator.example/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr("services.llm_service.AsyncOpenAI", lambda **_: client)
    monkeypatch.setattr(
        "services.llm_service.build_llm_provider_http_client", _validated_client
    )

    with pytest.raises(LLMServiceError, match="LLM API error during extraction"):
        await extract_action_items_and_summary(
            "email",
            "tenant-scoped-token",
            base_url="https://orchestrator.example/v1",
            model="orchestrator/free",
        )


async def _validated_client(*_):
    return "https://orchestrator.example/v1", None
