"""Tests for the grounded-answer endpoint and RAG citation enforcement."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import services.rag_service as rag_service


@pytest.mark.asyncio
async def test_call_llm_sends_openai_json_schema_response_format():
    """`_call_llm` must request OpenAI structured output for the answer shape.

    Proves the *local* contract: `_call_llm` passes `GroundedAnswerPayload` as
    `response_format` and the right `model`. It mocks `AsyncOpenAI` entirely,
    so it does not exercise the SDK's own Pydantic-to-JSON-schema
    serialization -- that is what
    `test_grounded_answer_payload_serializes_to_the_openai_json_schema_wire_envelope`
    below verifies directly, unmocked (Devin Review: the wire-format claim
    this docstring previously made here was not actually proven by this test).
    """
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.parsed = rag_service.GroundedAnswerPayload(
        answer="grounded", cited_email_ids=[1]
    )
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    with patch("services.rag_service.AsyncOpenAI", return_value=mock_client):
        result = await rag_service._call_llm(
            api_key="k",
            base_url=None,
            model="gpt-test",
            question="q",
            emails_json="{}",
        )

    assert result.answer == "grounded"
    call_kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs
    assert call_kwargs["response_format"] is rag_service.GroundedAnswerPayload
    assert call_kwargs["model"] == "gpt-test"


def test_grounded_answer_payload_serializes_to_the_openai_json_schema_wire_envelope():
    """Prove the actual wire envelope the OpenAI SDK sends, not just the local kwarg.

    Calls ``openai.lib._parsing.type_to_response_format_param`` directly, with
    no mocking, against the real ``GroundedAnswerPayload`` model -- the exact
    function ``.beta.chat.completions.parse()`` calls internally to build the
    request body.
    """
    from openai.lib._parsing import type_to_response_format_param

    envelope = type_to_response_format_param(rag_service.GroundedAnswerPayload)

    assert envelope["type"] == "json_schema"
    assert envelope["json_schema"]["name"] == "GroundedAnswerPayload"
    assert envelope["json_schema"]["strict"] is True
    schema = envelope["json_schema"]["schema"]
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"answer", "cited_email_ids"}
    assert schema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_call_llm_raises_on_unparsable_response():
    """A schema-violating completion must fail closed, not return corrupted data."""
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.parsed = None
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    with patch("services.rag_service.AsyncOpenAI", return_value=mock_client):
        with pytest.raises(RuntimeError, match="unparsable payload"):
            await rag_service._call_llm(
                api_key="k",
                base_url=None,
                model="gpt-test",
                question="q",
                emails_json="{}",
            )


def _context(email_id: int, content: str = "body") -> dict:
    return {
        "id": email_id,
        "subject": f"Subject {email_id}",
        "sender": "sender@example.com",
        "date": "2026-07-06",
        "content": content,
    }


@pytest.mark.asyncio
async def test_answer_returns_none_without_context(monkeypatch):
    call = AsyncMock()
    monkeypatch.setattr(rag_service, "_call_llm", call)

    result = await rag_service.answer_from_emails("question", [], api_key="k")

    assert result is None
    call.assert_not_awaited()  # no LLM call without retrieved evidence


@pytest.mark.asyncio
async def test_answer_keeps_only_citations_from_retrieved_set(monkeypatch):
    monkeypatch.setattr(
        rag_service,
        "_call_llm",
        AsyncMock(
            return_value=rag_service.GroundedAnswerPayload(
                answer="grounded answer",
                cited_email_ids=[1, 999],  # 999 was never retrieved
            )
        ),
    )

    result = await rag_service.answer_from_emails(
        "question", [_context(1), _context(2)], api_key="k", model="gpt-test"
    )

    assert result is not None
    assert result.answer == "grounded answer"
    assert result.cited_email_ids == [1]
    assert "gpt-test" in result.provenance


@pytest.mark.asyncio
async def test_answer_bounds_context_to_max_emails(monkeypatch):
    captured = {}

    async def fake_call(**kwargs):
        captured.update(kwargs)
        return rag_service.GroundedAnswerPayload(answer="a", cited_email_ids=[])

    monkeypatch.setattr(rag_service, "_call_llm", fake_call)

    contexts = [_context(i) for i in range(10)]
    await rag_service.answer_from_emails("question", contexts, api_key="k")

    assert captured["emails_json"].count("email_id") == rag_service.MAX_CONTEXT_EMAILS


@pytest.mark.asyncio
async def test_answer_truncates_long_content(monkeypatch):
    captured = {}

    async def fake_call(**kwargs):
        captured.update(kwargs)
        return rag_service.GroundedAnswerPayload(answer="a", cited_email_ids=[])

    monkeypatch.setattr(rag_service, "_call_llm", fake_call)

    await rag_service.answer_from_emails(
        "question", [_context(1, content="X" * 5000)], api_key="k"
    )

    assert "X" * rag_service.MAX_CONTENT_CHARS in captured["emails_json"]
    assert "X" * (rag_service.MAX_CONTENT_CHARS + 1) not in captured["emails_json"]


# ---- endpoint tests (reuse the search suite's mock plumbing) ----
from tests.test_search import override_get_db  # noqa: E402
from db.session import get_db, get_readonly_db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_readonly_db] = override_get_db
    with TestClient(app, headers={"X-User-Id": "testuser"}) as c:
        yield c
    app.dependency_overrides.clear()


@patch("api.search.answer_from_emails", new_callable=AsyncMock)
@patch("api.search.generate_embeddings", new_callable=AsyncMock)
def test_answer_endpoint_returns_grounded_answer_with_citations(
    mock_embeddings, mock_answer, client
):
    mock_embeddings.return_value = [[0.1] * 1536]
    mock_answer.return_value = rag_service.GroundedAnswer(
        answer="그 미팅은 화요일입니다.",
        cited_email_ids=[1],
        provenance="OpenAI (gpt-test)",
    )

    response = client.post("/api/search/answer", json={"query": "미팅 언제?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "그 미팅은 화요일입니다."
    assert [c["email_id"] for c in data["citations"]] == [1]
    assert data["citations"][0]["subject"] == "Test Subject"
    assert data["provenance"] == "OpenAI (gpt-test)"
    # The model only saw retrieved, owner-scoped content.
    context_arg = mock_answer.await_args.args[1]
    assert {email["id"] for email in context_arg} == {1}


@patch("api.search.answer_from_emails", new_callable=AsyncMock)
@patch("api.search.generate_embeddings", new_callable=AsyncMock)
def test_answer_endpoint_empty_query_short_circuits(
    mock_embeddings, mock_answer, client
):
    response = client.post("/api/search/answer", json={"query": "   "})

    assert response.status_code == 200
    assert response.json() == {"answer": None, "citations": [], "provenance": None}
    mock_answer.assert_not_awaited()
    mock_embeddings.assert_not_awaited()
