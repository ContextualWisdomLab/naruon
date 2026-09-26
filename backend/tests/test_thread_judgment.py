import pytest

from services.thread_judgment import (
    CitedStatement,
    JudgmentSegment,
    JudgmentTask,
    ThreadJudgmentDraft,
    UnresolvedTension,
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
