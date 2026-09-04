"""Execution-boundary regressions for the Task 9 email-writing review service."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from api.auth import AuthContext
from services.email_writing_candidate_review import (
    EmailWritingCandidateDiagnostic,
    EmailWritingCandidateOutput,
    EmailWritingCandidateReviewResult,
)
from services.email_writing_context_service import (
    EmailWritingContextBundle,
    EmailWritingMessageContext,
)
from services.email_writing_contracts import (
    EmailWritingDocumentGuidance,
    EmailWritingDocumentRevision,
    EmailWritingReviewRequest,
    EmailWritingTextPositionSelector,
)
from services.email_writing_judge import EmailWritingJudgeEvaluation
from services.email_writing_review_service import (
    EmailWritingReviewRuntimeProfile,
    EmailWritingReviewService,
)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 9, 2, 7, 30, tzinfo=UTC)
DRAFT = "Please send the signed report by Friday."
DIGEST = "a1" * 32


def _revision() -> EmailWritingDocumentRevision:
    return EmailWritingDocumentRevision(
        algorithm="SHA-256",
        digest_hex=DIGEST,
        strong_entity_tag=f'"sha256-{DIGEST}"',
    )


def _request() -> EmailWritingReviewRequest:
    return EmailWritingReviewRequest(
        source_email_id=41,
        document_revision=_revision(),
        projection_name="inkspan-prosemirror-text",
        projection_version=1,
        draft_plain_text=DRAFT,
        language_tag="en",
        review_mode="deep",
        reply_objective="Obtain the signed report by Friday.",
    )


def _bundle(request: EmailWritingReviewRequest) -> EmailWritingContextBundle:
    source = EmailWritingMessageContext(
        email_id=41,
        message_id="message-41@example.test",
        sent_at=NOW - datetime.timedelta(hours=1),
        subject="Signed report",
        sender_header="Reviewer <reviewer@example.test>",
        reply_to_header=None,
        recipient_header="Author <author@example.test>",
        body="Please return the signed report by Friday.",
        selected_source=True,
    )
    return EmailWritingContextBundle(
        selected_email_id=41,
        canonical_thread_id="thread-41@example.test",
        subject=source.subject,
        selected_source_message=source,
        chronological_messages=(source,),
        participant_roles=(),
        reply_objective=request.reply_objective,
        current_draft=request.draft_plain_text,
        declared_language_tag=request.language_tag,
        review_mode=request.review_mode,
        document_revision_digest=request.document_revision.digest_hex,
        projection_name=request.projection_name,
        projection_version=request.projection_version,
        context_limitations=(),
    )


def _candidate() -> EmailWritingCandidateDiagnostic:
    return EmailWritingCandidateDiagnostic(
        selector=EmailWritingTextPositionSelector(
            type="TextPositionSelector",
            start=0,
            end=6,
        ),
        category_code="clarity",
        priority="important",
        title="Clarify request",
        explanation="The proposed wording keeps the requested artifact and deadline explicit.",
        suggested_replacement="Please",
        candidate_confidence=0.99,
        candidate_evidence_ids=["draft"],
    )


class _CandidateReviewer:
    async def review(self, bundle: EmailWritingContextBundle) -> EmailWritingCandidateReviewResult:
        del bundle
        return EmailWritingCandidateReviewResult(
            output=EmailWritingCandidateOutput(
                diagnostics=[_candidate()],
                document_guidance=EmailWritingDocumentGuidance(
                    purpose_summary="Request the signed report by Friday.",
                    reader_interpretation="The recipient should return the signed report.",
                    missing_requests=[],
                    structure_suggestion="Keep the artifact and deadline together.",
                ),
                context_limitations=[],
                review_language="en",
                abstained_claims=[],
            ),
            orchestration_mode="conduct",
            prompt_hash="sha256:" + "b2" * 32,
            prompt_template_hash="sha256:" + "c3" * 32,
            candidate_payload_hash="sha256:" + "d4" * 32,
        )


class _Judge:
    def evaluate(self, *args: object, **kwargs: object) -> EmailWritingJudgeEvaluation:
        del args, kwargs
        criterion_ids = (
            "issue_support",
            "span_fidelity",
            "replacement_correctness",
            "intent_preservation",
            "fact_preservation",
            "request_strength_preservation",
            "audience_pragmatics",
            "technical_precision",
            "actionability",
            "explanation_quality",
        )
        return EmailWritingJudgeEvaluation(
            criterion_categories={criterion_id: 3 for criterion_id in criterion_ids},
            criterion_scores={criterion_id: 1.0 for criterion_id in criterion_ids},
            category_count=4,
            advisory_accepted=True,
            user_facing_admission="withheld",
            send_decision="not_applicable",
            candidate_confidence_used=False,
            payload_hash="sha256:" + "e5" * 32,
        )


class _BoundedJudgeExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def run_judge(self, operation, *args: object, **kwargs: object):
        self.calls += 1
        return operation(*args, **kwargs)


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _policy() -> Any:
    return SimpleNamespace(
        policy_version="email-writing-evaluation-only-v1",
        category_count=4,
        category_anchors=[
            "no_credible_evidence",
            "partial_or_weak_support",
            "mostly_supported_with_gaps",
            "fully_supported_with_accurate_evidence",
        ],
    )


@pytest.mark.asyncio
async def test_review_service_uses_injected_bounded_judge_executor() -> None:
    request = _request()
    bundle = _bundle(request)
    executor = _BoundedJudgeExecutor()

    async def build_context(*args: object) -> EmailWritingContextBundle:
        del args
        return bundle

    service = EmailWritingReviewService(
        candidate_reviewer=_CandidateReviewer(),
        independent_judge=_Judge(),
        judge_executor=executor,
        judge_policy=_policy(),
        runtime_profile=EmailWritingReviewRuntimeProfile(
            workflow_identifier="email_writing_review",
            workflow_version="1",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="independent-judge-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            maximum_candidates=4,
            total_wall_seconds=5.0,
        ),
        context_builder=build_context,
        policy_evaluator=lambda **kwargs: "withhold",
        confidence_mapper=lambda evaluation: min(evaluation.criterion_scores.values()),
        clock=lambda: NOW,
    )

    response = await service.review(
        _Session(),
        AuthContext(
            user_id="user-alpha",
            role="member",
            organization_id="organization-alpha",
            group_ids=(),
            workspace_id="workspace-alpha",
        ),
        request,
    )

    assert executor.calls == 1
    assert response.review_status == "abstained"
    assert response.diagnostics == []
