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
            [JudgmentTask(uid="real", title="Known task", status="open")],
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


@pytest.mark.asyncio
async def test_thread_judgment_closes_transport_when_sdk_construction_fails(monkeypatch):
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
