"""Review regressions for Task 9 service-owned trust and deadline boundaries."""

from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace

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
from services.email_writing_review_service import (
    EmailWritingReviewRuntimeProfile,
    EmailWritingReviewService,
    EmailWritingReviewServiceError,
)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
DRAFT = "Please send the signed report by Friday."
DIGEST = "f1" * 32


def _request() -> EmailWritingReviewRequest:
    revision = EmailWritingDocumentRevision(
        algorithm="SHA-256",
        digest_hex=DIGEST,
        strong_entity_tag=f'"sha256-{DIGEST}"',
    )
    return EmailWritingReviewRequest(
        source_email_id=41,
        document_revision=revision,
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


def _candidate_result(
    *,
    end: int = 6,
    evidence_id: str = "draft",
) -> EmailWritingCandidateReviewResult:
    diagnostic = EmailWritingCandidateDiagnostic(
        selector=EmailWritingTextPositionSelector(
            type="TextPositionSelector",
            start=0,
            end=end,
        ),
        category_code="clarity",
        priority="important",
        title="Clarify request",
        explanation="Keep the requested artifact and deadline explicit.",
        suggested_replacement="Please",
        candidate_confidence=0.99,
        candidate_evidence_ids=[evidence_id],
    )
    return EmailWritingCandidateReviewResult(
        output=EmailWritingCandidateOutput(
            diagnostics=[diagnostic],
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
        prompt_hash="sha256:" + "a2" * 32,
        prompt_template_hash="sha256:" + "b3" * 32,
        candidate_payload_hash="sha256:" + "c4" * 32,
    )


class _CandidatePort:
    def __init__(
        self,
        result: EmailWritingCandidateReviewResult,
        *,
        delay_seconds: float = 0.0,
    ) -> None:
        self.result = result
        self.delay_seconds = delay_seconds

    async def review(
        self,
        bundle: EmailWritingContextBundle,
    ) -> EmailWritingCandidateReviewResult:
        del bundle
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return self.result


class _JudgeMustNotRun:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, *args: object, **kwargs: object):
        del args, kwargs
        self.calls += 1
        raise AssertionError("Judge must not receive an invalid Candidate result")


class _JudgeExecutor:
    async def run_judge(self, operation, *args: object, **kwargs: object):
        return operation(*args, **kwargs)


class _Session:
    def __init__(self, *, block_commit: bool = False) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.block_commit = block_commit

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1
        if self.block_commit:
            await asyncio.Event().wait()

    async def rollback(self) -> None:
        self.rollbacks += 1


def _runtime(*, total_wall_seconds: float = 5.0) -> EmailWritingReviewRuntimeProfile:
    return EmailWritingReviewRuntimeProfile(
        workflow_identifier="email_writing_review",
        workflow_version="1",
        candidate_model_profile_id="candidate-reviewer-v1",
        candidate_provider_id="contextual-orchestrator",
        judge_model_profile_id="independent-judge-v1",
        judge_provider_id="contextual-orchestrator",
        rubric_version="email_writing_judge_rubric_v1",
        maximum_candidates=4,
        total_wall_seconds=total_wall_seconds,
    )


def _auth() -> AuthContext:
    return AuthContext(
        user_id="user-alpha",
        role="member",
        organization_id="organization-alpha",
        group_ids=(),
        workspace_id="workspace-alpha",
    )


def _policy() -> object:
    return SimpleNamespace(
        policy_version="email-writing-evaluation-only-v1",
        status="evaluation_only",
        publish_decision="withhold",
        category_count=4,
        category_anchors=["none", "weak", "mostly", "full"],
    )


def _service(
    request: EmailWritingReviewRequest,
    candidate_port: _CandidatePort,
    judge: _JudgeMustNotRun,
    *,
    total_wall_seconds: float = 5.0,
) -> EmailWritingReviewService:
    bundle = _bundle(request)

    async def build_context(*args: object) -> EmailWritingContextBundle:
        del args
        return bundle

    return EmailWritingReviewService(
        candidate_reviewer=candidate_port,
        independent_judge=judge,
        judge_executor=_JudgeExecutor(),
        judge_policy=_policy(),
        runtime_profile=_runtime(total_wall_seconds=total_wall_seconds),
        context_builder=build_context,
        policy_evaluator=lambda **kwargs: "withhold",
        confidence_mapper=None,
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("candidate_result", "expected_code"),
    [
        (
            _candidate_result(end=len(DRAFT) + 1),
            "candidate_selector_out_of_range",
        ),
        (
            _candidate_result(evidence_id="email:999"),
            "candidate_evidence_unknown",
        ),
    ],
)
async def test_injected_candidate_port_is_revalidated_against_authorized_bundle(
    candidate_result: EmailWritingCandidateReviewResult,
    expected_code: str,
) -> None:
    request = _request()
    judge = _JudgeMustNotRun()
    service = _service(request, _CandidatePort(candidate_result), judge)

    response = await service.review(_Session(), _auth(), request)

    assert judge.calls == 0
    assert response.review_status == "rejected"
    assert response.diagnostics == []
    assert expected_code in response.abstained_claims


@pytest.mark.asyncio
async def test_timeout_finalization_does_not_wait_unbounded_for_evidence_commit() -> None:
    request = _request()
    session = _Session(block_commit=True)
    service = _service(
        request,
        _CandidatePort(_candidate_result(), delay_seconds=0.02),
        _JudgeMustNotRun(),
        total_wall_seconds=0.01,
    )

    with pytest.raises(EmailWritingReviewServiceError) as caught:
        await asyncio.wait_for(service.review(session, _auth(), request), timeout=0.1)

    assert caught.value.code == "review_evidence_unavailable"
    assert session.commits == 1
    assert session.rollbacks == 1
