import json
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from services.llm_provider_selection import RuntimeLLMProvider
from services.thread_judgment import (
    CitedStatement,
    JudgmentSegment,
    JudgmentTask,
    JudgmentObject,
    ThreadJudgmentDraft,
    UnresolvedTension,
    synthesize_thread_judgment,
    validate_judgment_citations,
)


def test_thread_judgment_rejects_uncited_claims_and_one_message_tensions():
    segments = [
        JudgmentSegment(uid="a", message_id="first", text="The date is Monday."),
        JudgmentSegment(uid="b", message_id="second", text="The date is Tuesday."),
    ]
    card = ThreadJudgmentDraft(
        current_state=CitedStatement(
            text="The date conflicts", evidence_segment_uids=["a", "b"]
        ),
        judgment_point=None,
        recommended_action=None,
        blocking_dependencies=[],
        unresolved_commitments=[],
        tensions=[
            UnresolvedTension(
                description="Two dates remain unresolved",
                first_evidence_segment_uids=["a"],
                second_evidence_segment_uids=["b"],
            )
        ],
    )
    validate_judgment_citations(card, segments)

    card.current_state.evidence_segment_uids = ["unknown"]
    with pytest.raises(ValueError, match="unknown evidence"):
        validate_judgment_citations(card, segments)

    card.current_state.evidence_segment_uids = ["a"]
    card.tensions[0].first_evidence_segment_uids = ["a", "b"]
    card.tensions[0].second_evidence_segment_uids = ["a"]
    with pytest.raises(ValueError, match="two distinct source messages"):
        validate_judgment_citations(card, segments)

    card.tensions = []
    card.current_state.linked_task_uids = ["missing"]
    with pytest.raises(ValueError, match="unknown task"):
        validate_judgment_citations(
            card,
            segments,
            [
                JudgmentTask(
                    uid="real", title="Known task", status="open", message_id="first"
                )
            ],
        )

    card.current_state.linked_task_uids = []
    card.current_state.linked_object_uids = ["missing"]
    with pytest.raises(ValueError, match="unknown object"):
        validate_judgment_citations(
            card,
            segments,
            objects=[
                JudgmentObject(
                    uid="real",
                    title="Known object",
                    object_type="issue",
                    evidence_segment_uid="a",
                )
            ],
        )
    card.current_state.linked_object_uids = ["real"]
    with pytest.raises(ValueError, match="lacks cited evidence"):
        validate_judgment_citations(
            card,
            segments,
            objects=[
                JudgmentObject(
                    uid="real",
                    title="Different evidence",
                    object_type="issue",
                    evidence_segment_uid="b",
                )
            ],
        )


def test_thread_judgment_task_link_requires_its_source_message():
    segments = [
        JudgmentSegment(uid="a", message_id="first", text="A task was created."),
        JudgmentSegment(uid="b", message_id="second", text="Other news."),
    ]
    task = JudgmentTask(
        uid="task", title="Follow up", status="open", message_id="first"
    )
    card = ThreadJudgmentDraft(
        current_state=CitedStatement(
            text="Follow up", evidence_segment_uids=["b"], linked_task_uids=["task"]
        ),
        judgment_point=None,
        recommended_action=None,
        blocking_dependencies=[],
        unresolved_commitments=[],
        tensions=[],
    )

    with pytest.raises(ValueError, match="task lacks cited evidence"):
        validate_judgment_citations(card, segments, [task])
    card.current_state.evidence_segment_uids = ["a"]
    validate_judgment_citations(card, segments, [task])


@pytest.mark.asyncio
async def test_thread_judgment_closes_transport_when_sdk_construction_fails(
    monkeypatch,
):
    http_client = AsyncMock()

    async def build_client(_base_url):
        return None, http_client

    def fail_sdk_construction(**_kwargs):
        raise ValueError("invalid provider configuration")

    monkeypatch.setattr(
        "services.thread_judgment.build_llm_provider_http_client", build_client
    )
    monkeypatch.setattr("services.thread_judgment.AsyncOpenAI", fail_sdk_construction)
    provider = RuntimeLLMProvider(
        api_key="test",
        base_url=None,
        chat_model="test-model",
        embedding_model="test-embedding",
        provider_name="test",
        provider_source="tenant_config",
    )

    with pytest.raises(ValueError, match="invalid provider configuration"):
        await synthesize_thread_judgment([], [], [], provider)

    http_client.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_thread_judgment_keeps_earlier_citations_across_batches(monkeypatch):
    earlier = JudgmentSegment(uid="earlier", message_id="first", text="Monday")
    later = JudgmentSegment(uid="later", message_id="second", text="Tuesday")
    previous = ThreadJudgmentDraft(
        current_state=CitedStatement(text="Monday", evidence_segment_uids=["earlier"]),
        judgment_point=None,
        recommended_action=None,
        blocking_dependencies=[],
        unresolved_commitments=[],
        tensions=[],
    )
    combined = previous.model_copy(
        update={
            "tensions": [
                UnresolvedTension(
                    description="The dates conflict",
                    first_evidence_segment_uids=["earlier"],
                    second_evidence_segment_uids=["later"],
                )
            ]
        }
    )
    parse = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=combined))]
        )
    )
    client = SimpleNamespace(
        beta=SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))
        ),
        close=AsyncMock(),
    )

    async def build_client(_base_url):
        return None, AsyncMock()

    monkeypatch.setattr(
        "services.thread_judgment.build_llm_provider_http_client", build_client
    )
    monkeypatch.setattr("services.thread_judgment.AsyncOpenAI", lambda **_: client)
    provider = RuntimeLLMProvider(
        api_key="test",
        base_url=None,
        chat_model="test-model",
        embedding_model="test-embedding",
        provider_name="test",
        provider_source="tenant_config",
    )

    result = await synthesize_thread_judgment(
        [later], [], [], provider, previous=previous, known_segments=[earlier, later]
    )

    assert result == combined
    payload = json.loads(
        parse.await_args.kwargs["messages"][1]["content"].removeprefix(
            "THREAD_EVIDENCE_JSON "
        )
    )
    assert [segment["uid"] for segment in payload["segments"]] == ["later"]
    assert payload["earlier_judgment"]["current_state"]["evidence_segment_uids"] == [
        "earlier"
    ]
    client.close.assert_awaited_once_with()
