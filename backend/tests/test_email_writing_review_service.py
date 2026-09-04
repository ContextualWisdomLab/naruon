"""Task 9 contracts for bounded, fail-closed email-writing review composition."""

from __future__ import annotations

import asyncio
import datetime
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

import pytest

from api.auth import AuthContext
from db.email_writing_evidence import EmailReviewSession
from services.email_writing_candidate_review import (
    EmailWritingCandidateDiagnostic,
    EmailWritingCandidateError,
    EmailWritingCandidateOutput,
    EmailWritingCandidateReviewResult,
)
from services.email_writing_context_service import (
    EmailWritingContextBundle,
    EmailWritingContextError,
    EmailWritingMessageContext,
)
from services.email_writing_contracts import (
    EmailWritingDocumentGuidance,
    EmailWritingDocumentRevision,
    EmailWritingReviewRequest,
    EmailWritingTextPositionSelector,
)
from services.email_writing_judge import EmailWritingJudgeError, EmailWritingJudgeEvaluation
from services.email_writing_policy import EmailWritingPolicyError
import services.email_writing_review_service as review_service_module
from services.email_writing_review_service import (
    EmailWritingReviewRuntimeProfile,
    EmailWritingReviewService,
    EmailWritingReviewServiceError,
)

UTC = datetime.timezone.utc
REVISION_DIGEST = "7c" * 32
PROMPT_HASH = "sha256:" + "ab" * 32
CANDIDATE_HASH = "sha256:" + "cd" * 32
REPLACEMENT_HASH = "sha256:" + "de" * 32
EXPLANATION_HASH = "sha256:" + "ef" * 32
DRAFT = "Please send the signed report by Friday."
NOW = datetime.datetime(2026, 9, 2, 7, 0, tzinfo=UTC)


def _revision(digest: str = REVISION_DIGEST) -> EmailWritingDocumentRevision:
    return EmailWritingDocumentRevision(
        algorithm="SHA-256",
        digest_hex=digest,
        strong_entity_tag=f'"sha256-{digest}"',
    )


def _request(*, review_mode: str = "deep") -> EmailWritingReviewRequest:
    selector = None
    if review_mode == "incremental":
        selector = EmailWritingTextPositionSelector(
            type="TextPositionSelector",
            start=0,
            end=6,
        )
    return EmailWritingReviewRequest(
        source_email_id=41,
        document_revision=_revision(),
        projection_name="inkspan-prosemirror-text",
        projection_version=1,
        draft_plain_text=DRAFT,
        language_tag="en",
        review_mode=review_mode,
        changed_selector=selector,
        reply_objective="Obtain the signed report by the stated deadline.",
    )


def _bundle(
    request: EmailWritingReviewRequest,
    *,
    revision_digest: str | None = None,
) -> EmailWritingContextBundle:
    source = EmailWritingMessageContext(
        email_id=request.source_email_id,
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
        selected_email_id=request.source_email_id,
        canonical_thread_id="thread-41@example.test",
        subject=source.subject,
        selected_source_message=source,
        chronological_messages=(source,),
        participant_roles=(),
        reply_objective=request.reply_objective,
        current_draft=request.draft_plain_text,
        declared_language_tag=request.language_tag,
        review_mode=request.review_mode,
        document_revision_digest=revision_digest or request.document_revision.digest_hex,
        projection_name=request.projection_name,
        projection_version=request.projection_version,
        context_limitations=(),
    )


def _guidance() -> EmailWritingDocumentGuidance:
    return EmailWritingDocumentGuidance(
        purpose_summary="The draft requests a signed report by Friday.",
        reader_interpretation="The recipient is expected to return the signed report.",
        missing_requests=[],
        structure_suggestion="Keep the request and deadline together.",
    )


def _candidate(
    *,
    start: int = 0,
    end: int = 6,
    title: str = "Clarify request",
) -> EmailWritingCandidateDiagnostic:
    return EmailWritingCandidateDiagnostic(
        selector=EmailWritingTextPositionSelector(
            type="TextPositionSelector",
            start=start,
            end=end,
        ),
        category_code="clarity",
        priority="important",
        title=title,
        explanation="The proposed wording keeps the requested artifact and deadline explicit.",
        suggested_replacement="Please",
        candidate_confidence=0.99,
        candidate_evidence_ids=["draft"],
    )


def _candidate_result(
    *diagnostics: EmailWritingCandidateDiagnostic,
) -> EmailWritingCandidateReviewResult:
    return EmailWritingCandidateReviewResult(
        output=EmailWritingCandidateOutput(
            diagnostics=list(diagnostics),
            document_guidance=_guidance(),
            context_limitations=[],
            review_language="en",
            abstained_claims=[],
        ),
        orchestration_mode="conduct",
        prompt_hash="sha256:" + "b2" * 32,
        prompt_template_hash="sha256:" + "c3" * 32,
        candidate_payload_hash="sha256:" + "d4" * 32,
    )


def _judge_evaluation(score: float = 1.0) -> EmailWritingJudgeEvaluation:
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
        criterion_scores={criterion_id: score for criterion_id in criterion_ids},
        category_count=4,
        advisory_accepted=True,
        user_facing_admission="withheld",
        send_decision="not_applicable",
        candidate_confidence_used=False,
        payload_hash="sha256:" + "e5" * 32,
    )


def _policy() -> Any:
    return SimpleNamespace(
        policy_version="email-writing-evaluation-only-v1",
        status="evaluation_only",
        publish_decision="withhold",
        category_count=4,
        category_anchors=[
            "no_credible_evidence",
            "partial_or_weak_support",
            "mostly_supported_with_gaps",
            "fully_supported_with_accurate_evidence",
        ],
    )


def _runtime(**overrides: object) -> EmailWritingReviewRuntimeProfile:
    values: dict[str, object] = {
        "workflow_identifier": "email_writing_review",
        "workflow_version": "1",
        "candidate_model_profile_id": "candidate-reviewer-v1",
        "candidate_provider_id": "contextual-orchestrator",
        "judge_model_profile_id": "independent-judge-v1",
        "judge_provider_id": "contextual-orchestrator",
        "rubric_version": "email_writing_judge_rubric_v1",
        "maximum_candidates": 4,
        "total_wall_seconds": 5.0,
    }
    values.update(overrides)
    return EmailWritingReviewRuntimeProfile(**values)


@dataclass
class _CandidateReviewer:
    result: EmailWritingCandidateReviewResult | None = None
    error: BaseException | None = None
    delay_seconds: float = 0.0
    calls: int = 0

    async def review(
        self,
        bundle: EmailWritingContextBundle,
    ) -> EmailWritingCandidateReviewResult:
        self.calls += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        expected_mode = "route" if bundle.review_mode == "incremental" else "conduct"
        if self.result.orchestration_mode != expected_mode:
            return EmailWritingCandidateReviewResult(
                output=self.result.output,
                orchestration_mode=expected_mode,
                prompt_hash=self.result.prompt_hash,
                prompt_template_hash=self.result.prompt_template_hash,
                candidate_payload_hash=self.result.candidate_payload_hash,
            )
        return self.result


class _Judge:
    def __init__(
        self,
        evaluations: list[EmailWritingJudgeEvaluation | BaseException],
    ) -> None:
        self._evaluations = list(evaluations)
        self.calls = 0

    def evaluate(self, *args: object, **kwargs: object) -> EmailWritingJudgeEvaluation:
        del args, kwargs
        result = self._evaluations[self.calls]
        self.calls += 1
        if isinstance(result, BaseException):
            raise result
        return result


class _JudgeExecutor:
    """Deterministic stand-in for Task 5's bounded Judge worker lane."""

    def __init__(self) -> None:
        self.calls = 0

    async def run_judge(self, operation, *args: object, **kwargs: object):
        self.calls += 1
        return operation(*args, **kwargs)


class _Session:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = fail_commit

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("database unavailable with secret payload that must not escape")

    async def rollback(self) -> None:
        self.rollbacks += 1


def _auth() -> AuthContext:
    return AuthContext(
        user_id="user-alpha",
        role="member",
        organization_id="organization-alpha",
        group_ids=(),
        workspace_id="workspace-alpha",
    )


def _builder_for(bundle: EmailWritingContextBundle):
    async def build(
        session: object,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
    ) -> EmailWritingContextBundle:
        del session, auth_context, request
        return bundle

    return build


def _service(
    *,
    request: EmailWritingReviewRequest,
    candidate_reviewer: _CandidateReviewer,
    judge: _Judge,
    policy_outcome: str = "withhold",
    session: _Session | None = None,
    runtime: EmailWritingReviewRuntimeProfile | None = None,
    bundle: EmailWritingContextBundle | None = None,
) -> tuple[EmailWritingReviewService, _Session]:
    evidence_session = session or _Session()

    def evaluate_policy(**kwargs: object) -> str:
        del kwargs
        return policy_outcome

    service = EmailWritingReviewService(
        candidate_reviewer=candidate_reviewer,
        independent_judge=judge,
        judge_executor=_JudgeExecutor(),
        judge_policy=_policy(),
        runtime_profile=runtime or _runtime(),
        context_builder=_builder_for(bundle or _bundle(request)),
        policy_evaluator=evaluate_policy,
        confidence_mapper=lambda evaluation: min(evaluation.criterion_scores.values()),
        clock=lambda: NOW,
    )
    return service, evidence_session


def _persisted_session(session: _Session) -> EmailReviewSession:
    records = [item for item in session.added if isinstance(item, EmailReviewSession)]
    assert len(records) == 1
    return records[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("review_mode", ["incremental", "deep"])
async def test_withheld_policy_runs_candidate_and_judge_but_returns_no_semantic_guidance(
    review_mode: str,
) -> None:
    request = _request(review_mode=review_mode)
    candidate_reviewer = _CandidateReviewer(result=_candidate_result(_candidate()))
    judge = _Judge([_judge_evaluation()])
    service, session = _service(
        request=request,
        candidate_reviewer=candidate_reviewer,
        judge=judge,
        policy_outcome="withhold",
    )

    response = await service.review(session, _auth(), request)

    assert candidate_reviewer.calls == 1
    assert judge.calls == 1
    assert response.review_status == "abstained"
    assert response.diagnostics == []
    assert response.document_guidance.purpose_summary == ""
    assert response.document_guidance.reader_interpretation == ""
    assert response.document_guidance.missing_requests == []
    assert response.document_guidance.structure_suggestion == ""
    assert "policy_withhold" in response.abstained_claims
    persisted = _persisted_session(session)
    assert persisted.review_status == "abstained"
    assert persisted.review_mode == review_mode
    assert len(persisted.writing_diagnostic_records) == 1
    assert persisted.writing_diagnostic_records[0].admission_status == "abstained"
    assert persisted.writing_diagnostic_records[0].admission_reason_code == "policy_withhold"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_all_admitted_candidates_return_revision_bound_diagnostics_only_after_policy() -> None:
    request = _request()
    candidate_reviewer = _CandidateReviewer(result=_candidate_result(_candidate()))
    judge = _Judge([_judge_evaluation(score=0.8)])
    service, session = _service(
        request=request,
        candidate_reviewer=candidate_reviewer,
        judge=judge,
        policy_outcome="admit",
    )

    response = await service.review(session, _auth(), request)

    assert response.review_status == "completed"
    assert len(response.diagnostics) == 1
    diagnostic = response.diagnostics[0]
    assert diagnostic.document_revision == request.document_revision
    assert diagnostic.selector.start == 0
    assert diagnostic.selector.end == 6
    assert diagnostic.confidence == pytest.approx(0.8)
    assert diagnostic.title == "Clarify request"
    assert response.document_guidance == _guidance()
    persisted = _persisted_session(session)
    assert persisted.review_status == "completed"
    stored = persisted.writing_diagnostic_records[0]
    assert stored.admission_status == "admitted"
    assert stored.judge_score == pytest.approx(0.8)
    assert DRAFT not in repr(persisted)
    assert DRAFT not in repr(stored)


@pytest.mark.asyncio
async def test_partial_judge_failure_is_atomic_and_does_not_leak_first_candidate() -> None:
    request = _request()
    candidate_reviewer = _CandidateReviewer(
        result=_candidate_result(
            _candidate(start=0, end=6, title="First"),
            _candidate(start=7, end=11, title="Second"),
        )
    )
    judge = _Judge(
        [
            _judge_evaluation(score=1.0),
            EmailWritingJudgeError("judge_runner_failed"),
        ]
    )
    service, session = _service(
        request=request,
        candidate_reviewer=candidate_reviewer,
        judge=judge,
        policy_outcome="admit",
    )

    response = await service.review(session, _auth(), request)

    assert judge.calls == 2
    assert response.review_status == "abstained"
    assert response.diagnostics == []
    assert "judge_runner_failed" in response.abstained_claims
    persisted = _persisted_session(session)
    assert persisted.review_status == "abstained"
    assert all(
        record.admission_status == "abstained"
        for record in persisted.writing_diagnostic_records
    )
    assert all(
        record.admission_reason_code == "judge_runner_failed"
        for record in persisted.writing_diagnostic_records
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy_outcome", "expected_status", "expected_code"),
    [
        ("unsupported_profile", "abstained", "unsupported_profile"),
        ("adjudicate", "judge_disagreement", "policy_adjudication_required"),
        ("policy_unavailable", "unavailable", "policy_unavailable"),
    ],
)
async def test_non_admission_policy_outcomes_fail_closed_for_the_whole_review(
    policy_outcome: str,
    expected_status: str,
    expected_code: str,
) -> None:
    request = _request()
    service, session = _service(
        request=request,
        candidate_reviewer=_CandidateReviewer(result=_candidate_result(_candidate())),
        judge=_Judge([_judge_evaluation()]),
        policy_outcome=policy_outcome,
    )

    response = await service.review(session, _auth(), request)

    assert response.review_status == expected_status
    assert response.diagnostics == []
    assert expected_code in response.abstained_claims


@pytest.mark.asyncio
async def test_stale_context_metadata_is_rejected_before_candidate_model_call() -> None:
    request = _request()
    reviewer = _CandidateReviewer(result=_candidate_result(_candidate()))
    service, session = _service(
        request=request,
        candidate_reviewer=reviewer,
        judge=_Judge([_judge_evaluation()]),
        bundle=_bundle(request, revision_digest="f0" * 32),
    )

    response = await service.review(session, _auth(), request)

    assert reviewer.calls == 0
    assert response.review_status == "stale"
    assert response.diagnostics == []
    assert "review_revision_stale" in response.abstained_claims
    assert _persisted_session(session).review_status == "stale"


@pytest.mark.asyncio
async def test_invalid_candidate_and_provider_outage_never_trigger_lexical_fallback() -> None:
    request = _request()
    for error, expected_status in (
        (EmailWritingCandidateError("candidate_payload_invalid"), "rejected"),
        (RuntimeError("provider outage and raw provider detail"), "unavailable"),
    ):
        reviewer = _CandidateReviewer(error=error)
        service, session = _service(
            request=request,
            candidate_reviewer=reviewer,
            judge=_Judge([_judge_evaluation()]),
        )

        response = await service.review(session, _auth(), request)

        assert response.review_status == expected_status
        assert response.diagnostics == []
        rendered = repr(response) + repr(_persisted_session(session))
        assert "provider outage and raw provider detail" not in rendered
        assert "keyword" not in rendered.lower()


@pytest.mark.asyncio
async def test_no_candidate_output_abstains_instead_of_exposing_unjudged_document_guidance() -> None:
    request = _request()
    service, session = _service(
        request=request,
        candidate_reviewer=_CandidateReviewer(result=_candidate_result()),
        judge=_Judge([]),
    )

    response = await service.review(session, _auth(), request)

    assert response.review_status == "abstained"
    assert response.diagnostics == []
    assert response.document_guidance.purpose_summary == ""
    assert "candidate_empty" in response.abstained_claims


@pytest.mark.asyncio
async def test_total_wall_timeout_returns_unavailable_without_unrecorded_diagnostics() -> None:
    request = _request()
    reviewer = _CandidateReviewer(
        result=_candidate_result(_candidate()),
        delay_seconds=0.05,
    )
    service, session = _service(
        request=request,
        candidate_reviewer=reviewer,
        judge=_Judge([_judge_evaluation()]),
        runtime=_runtime(total_wall_seconds=0.01),
    )

    response = await service.review(session, _auth(), request)

    assert response.review_status == "unavailable"
    assert response.diagnostics == []
    assert "review_timeout" in response.abstained_claims
    assert _persisted_session(session).review_status == "unavailable"


@pytest.mark.asyncio
async def test_candidate_count_limit_fails_closed_before_judge_calls() -> None:
    request = _request()
    candidates = tuple(
        _candidate(start=index * 2, end=index * 2 + 1, title=f"Candidate {index}")
        for index in range(3)
    )
    judge = _Judge([_judge_evaluation()] * 3)
    service, session = _service(
        request=request,
        candidate_reviewer=_CandidateReviewer(result=_candidate_result(*candidates)),
        judge=judge,
        runtime=_runtime(maximum_candidates=2),
    )

    response = await service.review(session, _auth(), request)

    assert judge.calls == 0
    assert response.review_status == "abstained"
    assert response.diagnostics == []
    assert "candidate_limit_exceeded" in response.abstained_claims


@pytest.mark.asyncio
async def test_policy_validation_exception_becomes_redacted_unavailable_review() -> None:
    request = _request()
    session = _Session()

    def fail_policy(**kwargs: object) -> str:
        del kwargs
        raise EmailWritingPolicyError("criterion_identity_mismatch")

    service = EmailWritingReviewService(
        candidate_reviewer=_CandidateReviewer(result=_candidate_result(_candidate())),
        independent_judge=_Judge([_judge_evaluation()]),
        judge_executor=_JudgeExecutor(),
        judge_policy=_policy(),
        runtime_profile=_runtime(),
        context_builder=_builder_for(_bundle(request)),
        policy_evaluator=fail_policy,
        confidence_mapper=lambda evaluation: min(evaluation.criterion_scores.values()),
        clock=lambda: NOW,
    )

    response = await service.review(session, _auth(), request)

    assert response.review_status == "unavailable"
    assert response.diagnostics == []
    assert "policy_validation_failed" in response.abstained_claims


@pytest.mark.asyncio
async def test_persistence_failure_rolls_back_and_returns_no_unrecorded_diagnostics() -> None:
    request = _request()
    session = _Session(fail_commit=True)
    service, _ = _service(
        request=request,
        candidate_reviewer=_CandidateReviewer(result=_candidate_result(_candidate())),
        judge=_Judge([_judge_evaluation()]),
        policy_outcome="admit",
        session=session,
    )

    with pytest.raises(EmailWritingReviewServiceError) as captured:
        await service.review(session, _auth(), request)

    assert captured.value.code == "review_evidence_unavailable"
    assert session.rollbacks == 1
    assert "secret payload" not in repr(captured.value)


@pytest.mark.asyncio
async def test_cancellation_persists_abstained_session_and_propagates_cancellation() -> None:
    request = _request()
    session = _Session()
    reviewer = _CandidateReviewer(
        result=_candidate_result(_candidate()),
        delay_seconds=10.0,
    )
    service, _ = _service(
        request=request,
        candidate_reviewer=reviewer,
        judge=_Judge([_judge_evaluation()]),
        session=session,
        runtime=_runtime(total_wall_seconds=30.0),
    )

    task = asyncio.create_task(service.review(session, _auth(), request))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    persisted = _persisted_session(session)
    assert persisted.review_status == "abstained"
    assert session.commits == 1


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"workflow_identifier": ""}, "review_runtime_identity_invalid"),
        ({"maximum_candidates": 0}, "review_candidate_limit_invalid"),
        ({"total_wall_seconds": float("nan")}, "review_wall_time_invalid"),
    ],
)
def test_runtime_profile_rejects_invalid_boundaries(
    overrides: dict[str, object],
    expected_code: str,
) -> None:
    with pytest.raises(ValueError, match=expected_code):
        _runtime(**overrides)


def test_review_helpers_cover_fail_closed_edge_values() -> None:
    request = _request()
    bundle = _bundle(request)
    without_replacement = _candidate_result(
        _candidate().model_copy(update={"suggested_replacement": None})
    )

    assert review_service_module._utc_now().tzinfo is UTC
    assert review_service_module._stable_unique(["", "a", "a", "b"]) == ["a", "b"]
    assert (
        review_service_module._candidate_kind(without_replacement.output.diagnostics[0])
        == "no_replacement_diagnostic"
    )

    wrong_mode = replace(_candidate_result(_candidate()), orchestration_mode="route")
    with pytest.raises(EmailWritingReviewServiceError, match="candidate_orchestration_mode_invalid"):
        review_service_module._validate_candidate_result_binding(request, bundle, wrong_mode)

    language_result = _candidate_result(_candidate())
    wrong_language = replace(
        language_result,
        output=language_result.output.model_copy(update={"review_language": "ko"}),
    )
    with pytest.raises(EmailWritingReviewServiceError, match="candidate_language_mismatch"):
        review_service_module._validate_candidate_result_binding(
            request, bundle, wrong_language
        )

    for invalid_confidence in (True, float("inf"), -0.1):
        with pytest.raises(
            EmailWritingReviewServiceError,
            match="review_confidence_unavailable",
        ):
            review_service_module._validate_confidence(invalid_confidence)


@pytest.mark.asyncio
async def test_owner_context_and_clock_fail_closed_boundaries() -> None:
    request = _request()
    reviewer = _CandidateReviewer(result=_candidate_result(_candidate()))
    service, session = _service(
        request=request,
        candidate_reviewer=reviewer,
        judge=_Judge([_judge_evaluation()]),
    )
    missing_owner = _auth().__class__(
        user_id="user-alpha",
        role="member",
        organization_id=None,
        group_ids=(),
        workspace_id="workspace-alpha",
    )
    with pytest.raises(EmailWritingReviewServiceError, match="review_owner_scope_unavailable"):
        await service.review(session, missing_owner, request)

    naive_clock_service, _ = _service(
        request=request,
        candidate_reviewer=reviewer,
        judge=_Judge([_judge_evaluation()]),
    )
    naive_clock_service._clock = lambda: NOW.replace(tzinfo=None)
    with pytest.raises(EmailWritingReviewServiceError, match="review_clock_invalid"):
        await naive_clock_service.review(_Session(), _auth(), request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context_error", "expected_code"),
    [
        (
            EmailWritingContextError(
                "email_unavailable", reason_code="selected_email_missing"
            ),
            "email_unavailable",
        ),
        (
            EmailWritingContextError(
                "context_insufficient", reason_code="thread_context_empty"
            ),
            "context_insufficient",
        ),
    ],
)
async def test_context_builder_errors_remain_redacted(
    context_error: EmailWritingContextError,
    expected_code: str,
) -> None:
    request = _request()

    async def fail_context(*args: object) -> EmailWritingContextBundle:
        del args
        raise context_error

    service = EmailWritingReviewService(
        candidate_reviewer=_CandidateReviewer(result=_candidate_result(_candidate())),
        independent_judge=_Judge([_judge_evaluation()]),
        judge_executor=_JudgeExecutor(),
        judge_policy=_policy(),
        runtime_profile=_runtime(),
        context_builder=fail_context,
        policy_evaluator=lambda **kwargs: "withhold",
        confidence_mapper=lambda evaluation: 1.0,
        clock=lambda: NOW,
    )
    session = _Session()

    if expected_code == "email_unavailable":
        with pytest.raises(EmailWritingReviewServiceError, match=expected_code):
            await service.review(session, _auth(), request)
    else:
        response = await service.review(session, _auth(), request)
        assert response.review_status == expected_code
        assert expected_code in response.abstained_claims


@pytest.mark.asyncio
async def test_unexpected_judge_policy_and_missing_confidence_fail_closed() -> None:
    request = _request()
    for judge_result, policy_evaluator, confidence_mapper, expected_code in (
        (RuntimeError("judge detail"), lambda **kwargs: "admit", lambda value: 1.0, "judge_runner_failed"),
        (_judge_evaluation(), lambda **kwargs: (_ for _ in ()).throw(RuntimeError("policy detail")), lambda value: 1.0, "policy_unavailable"),
        (_judge_evaluation(), lambda **kwargs: "admit", None, "review_confidence_unavailable"),
    ):
        service = EmailWritingReviewService(
            candidate_reviewer=_CandidateReviewer(result=_candidate_result(_candidate())),
            independent_judge=_Judge([judge_result]),
            judge_executor=_JudgeExecutor(),
            judge_policy=_policy(),
            runtime_profile=_runtime(),
            context_builder=_builder_for(_bundle(request)),
            policy_evaluator=policy_evaluator,
            confidence_mapper=confidence_mapper,
            clock=lambda: NOW,
        )
        response = await service.review(_Session(), _auth(), request)
        assert response.review_status in {"abstained", "unavailable"}
        assert expected_code in response.abstained_claims


@pytest.mark.asyncio
async def test_pre_context_timeout_and_cancellation_do_not_claim_evidence() -> None:
    request = _request()

    async def block_context(*args: object) -> EmailWritingContextBundle:
        del args
        await asyncio.sleep(1.0)
        raise AssertionError("unreachable")

    service = EmailWritingReviewService(
        candidate_reviewer=_CandidateReviewer(result=_candidate_result(_candidate())),
        independent_judge=_Judge([_judge_evaluation()]),
        judge_executor=_JudgeExecutor(),
        judge_policy=_policy(),
        runtime_profile=_runtime(total_wall_seconds=0.01),
        context_builder=block_context,
        policy_evaluator=lambda **kwargs: "withhold",
        confidence_mapper=lambda evaluation: 1.0,
        clock=lambda: NOW,
    )
    session = _Session()

    with pytest.raises(EmailWritingReviewServiceError, match="review_timeout"):
        await service.review(session, _auth(), request)
    assert session.added == []

    cancellation = asyncio.create_task(service.review(session, _auth(), request))
    await asyncio.sleep(0)
    cancellation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancellation
    assert session.added == []


@pytest.mark.asyncio
async def test_candidate_binding_and_persistence_owner_checks_fail_closed() -> None:
    request = _request()

    class WrongModeCandidate:
        async def review(
            self, bundle: EmailWritingContextBundle
        ) -> EmailWritingCandidateReviewResult:
            del bundle
            return replace(
                _candidate_result(_candidate()), orchestration_mode="route"
            )

    service = EmailWritingReviewService(
        candidate_reviewer=WrongModeCandidate(),
        independent_judge=_Judge([_judge_evaluation()]),
        judge_executor=_JudgeExecutor(),
        judge_policy=_policy(),
        runtime_profile=_runtime(),
        context_builder=_builder_for(_bundle(request)),
        policy_evaluator=lambda **kwargs: "withhold",
        confidence_mapper=lambda evaluation: 1.0,
        clock=lambda: NOW,
    )
    response = await service.review(_Session(), _auth(), request)
    assert response.review_status == "rejected"
    assert "candidate_orchestration_mode_invalid" in response.abstained_claims

    missing_owner = replace(_auth(), organization_id=None)
    with pytest.raises(EmailWritingReviewServiceError, match="review_owner_scope_unavailable"):
        await service._persist_review(
            _Session(),
            missing_owner,
            request,
            candidate_result=None,
            review_status="abstained",
            diagnostics=(),
        )


@pytest.mark.asyncio
async def test_rollback_cleanup_swallows_secondary_failure() -> None:
    class BrokenRollbackSession(_Session):
        async def rollback(self) -> None:
            raise RuntimeError("rollback detail")

    await review_service_module._rollback_bounded(BrokenRollbackSession())
