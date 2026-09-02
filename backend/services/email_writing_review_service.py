"""Compose bounded contextual email-writing review without becoming a send gate.

The service coordinates server-authoritative context, a contextual LLM Candidate,
an independent criterion Judge, structured policy admission, deterministic document
integrity checks, and privacy-minimized evidence. It never creates semantic
judgments from lexical rules, never returns unjudged Candidate output as guidance,
and never mutates or sends mail.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import datetime
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Protocol
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext
from db.email_writing_evidence import EmailReviewSession, WritingDiagnosticRecord
from services.email_writing_candidate_review import (
    EmailWritingCandidateDiagnostic,
    EmailWritingCandidateError,
    EmailWritingCandidateReviewResult,
    EmailWritingCandidateReviewer,
    _validate_candidate_selectors_and_evidence,
)
from services.email_writing_context_service import (
    EmailWritingContextBundle,
    EmailWritingContextError,
    build_email_writing_context,
)
from services.email_writing_contracts import (
    EmailWritingDiagnostic,
    EmailWritingDocumentGuidance,
    EmailWritingProvenance,
    EmailWritingReviewRequest,
    EmailWritingReviewResponse,
    ReviewStatus,
)
from services.email_writing_judge import (
    EmailWritingIndependentJudge,
    EmailWritingJudgeError,
    EmailWritingJudgeEvaluation,
)
from services.email_writing_policy import (
    AdmissionOutcome,
    EmailWritingJudgePolicy,
    EmailWritingPolicyError,
    evaluate_policy_admission,
)

EMAIL_WRITING_REVIEW_RETENTION_DAYS = 30
EMAIL_WRITING_REVIEW_DEFAULT_MAXIMUM_CANDIDATES = 16
EMAIL_WRITING_REVIEW_DEFAULT_TOTAL_WALL_SECONDS = 45.0
EMAIL_WRITING_REVIEW_TIMEOUT_EVIDENCE_SECONDS = 1.0
EMAIL_WRITING_REVIEW_ROLLBACK_SECONDS = 0.05
_EMPTY_PROMPT_HASH = "sha256:" + hashlib.sha256(b"").hexdigest()


class EmailWritingReviewServiceError(RuntimeError):
    """Payload-redacted failure that cannot safely become a review response."""

    def __init__(self, code: str) -> None:
        """Create one stable public error code without preserving causal text."""
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        """Return a representation containing only the stable error code."""
        return f"EmailWritingReviewServiceError({self.code!r})"


@dataclass(frozen=True, slots=True)
class EmailWritingReviewRuntimeProfile:
    """Explicit bounded runtime identities and budgets for one review workflow."""

    workflow_identifier: str
    workflow_version: str
    candidate_model_profile_id: str
    candidate_provider_id: str
    judge_model_profile_id: str
    judge_provider_id: str
    rubric_version: str
    maximum_candidates: int = EMAIL_WRITING_REVIEW_DEFAULT_MAXIMUM_CANDIDATES
    total_wall_seconds: float = EMAIL_WRITING_REVIEW_DEFAULT_TOTAL_WALL_SECONDS

    def __post_init__(self) -> None:
        """Reject non-positive or non-finite execution budgets before model work."""
        identity_values = (
            self.workflow_identifier,
            self.workflow_version,
            self.candidate_model_profile_id,
            self.candidate_provider_id,
            self.judge_model_profile_id,
            self.judge_provider_id,
            self.rubric_version,
        )
        if any(not value or len(value) > 128 for value in identity_values):
            raise ValueError("review_runtime_identity_invalid")
        if type(self.maximum_candidates) is not int or self.maximum_candidates <= 0:
            raise ValueError("review_candidate_limit_invalid")
        if (
            type(self.total_wall_seconds) not in {int, float}
            or type(self.total_wall_seconds) is bool
            or not math.isfinite(float(self.total_wall_seconds))
            or float(self.total_wall_seconds) <= 0.0
        ):
            raise ValueError("review_wall_time_invalid")


class EmailWritingReviewCandidatePort(Protocol):
    """Candidate-review surface consumed by the Task 9 composition service."""

    async def review(
        self,
        bundle: EmailWritingContextBundle,
    ) -> EmailWritingCandidateReviewResult:
        """Return one strictly parsed contextual Candidate result."""


class EmailWritingReviewJudgePort(Protocol):
    """Independent synchronous Judge surface executed off the event loop."""

    def evaluate(
        self,
        diagnostic: EmailWritingCandidateDiagnostic,
        bundle: EmailWritingContextBundle,
        *,
        candidate_model_profile_id: str,
        judge_model_profile_id: str,
        category_count: int,
        category_anchors: tuple[str, ...],
    ) -> EmailWritingJudgeEvaluation:
        """Return structured criterion evidence without user-facing admission."""


class EmailWritingReviewJudgeExecutorPort(Protocol):
    """Bounded Task-5-compatible execution lane for synchronous Judge work."""

    async def run_judge(
        self,
        operation: Callable[..., EmailWritingJudgeEvaluation],
        *args: object,
        **kwargs: object,
    ) -> EmailWritingJudgeEvaluation:
        """Run one Judge operation without consuming the FastAPI event-loop thread."""


class _ReviewEvidenceSession(Protocol):
    """Small persistence surface shared by AsyncSession and deterministic tests."""

    def add(self, value: object) -> None:
        """Stage one aggregate root for atomic persistence."""

    async def commit(self) -> None:
        """Commit the complete review evidence transaction."""

    async def rollback(self) -> None:
        """Roll back staged review evidence after a persistence failure."""


ContextBuilder = Callable[
    [AsyncSession | _ReviewEvidenceSession, AuthContext, EmailWritingReviewRequest],
    Awaitable[EmailWritingContextBundle],
]
PolicyEvaluator = Callable[..., AdmissionOutcome]
ConfidenceMapper = Callable[[EmailWritingJudgeEvaluation], float]
Clock = Callable[[], datetime.datetime]


@dataclass(frozen=True, slots=True)
class _EvaluatedCandidate:
    """One Candidate plus Judge evidence and structured policy outcome."""

    diagnostic: EmailWritingCandidateDiagnostic
    evaluation: EmailWritingJudgeEvaluation
    outcome: AdmissionOutcome
    diagnostic_identifier: str


@dataclass(frozen=True, slots=True)
class _PersistenceDiagnostic:
    """Privacy-minimized metadata required to persist one evaluated Candidate."""

    diagnostic: EmailWritingCandidateDiagnostic
    evaluation: EmailWritingJudgeEvaluation | None
    diagnostic_identifier: str
    admission_status: str
    admission_reason_code: str


def _utc_now() -> datetime.datetime:
    """Return a timezone-aware clock value for retention calculations."""
    return datetime.datetime.now(datetime.timezone.utc)


def _sha256_text(value: str) -> str:
    """Hash sensitive text before persistence without returning the plaintext."""
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    """Hash one canonical JSON-compatible value without persisting its contents."""
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(canonical)


def _empty_document_guidance() -> EmailWritingDocumentGuidance:
    """Return a schema-valid response that makes no semantic writing claim."""
    return EmailWritingDocumentGuidance(
        purpose_summary="",
        reader_interpretation="",
        missing_requests=[],
        structure_suggestion="",
    )


def _stable_unique(values: list[str]) -> list[str]:
    """Preserve first occurrence order for bounded non-semantic status codes."""
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _expected_orchestration_mode(request: EmailWritingReviewRequest) -> str:
    """Map explicit review mode to the already-published orchestration contract."""
    return "route" if request.review_mode == "incremental" else "conduct"


def _candidate_kind(diagnostic: EmailWritingCandidateDiagnostic) -> str:
    """Classify only the structural presence of a replacement field."""
    replacement = diagnostic.suggested_replacement
    if replacement is None or replacement == "":
        return "no_replacement_diagnostic"
    return "replacement_diagnostic"


def _overall_judge_score(evaluation: EmailWritingJudgeEvaluation | None) -> float:
    """Return the conservative minimum criterion score for persisted evidence."""
    if evaluation is None or not evaluation.criterion_scores:
        return 0.0
    return min(float(value) for value in evaluation.criterion_scores.values())


def _criterion_category_receipt(
    evaluation: EmailWritingJudgeEvaluation | None,
) -> list[str]:
    """Serialize criterion identities/categories without authored or model text."""
    if evaluation is None:
        return []
    return [
        f"{criterion_id}:{evaluation.criterion_categories[criterion_id]}"
        for criterion_id in sorted(evaluation.criterion_categories)
    ]


async def _rollback_bounded(session: _ReviewEvidenceSession) -> None:
    """Bound rollback cleanup so a failing evidence path cannot hang review return."""
    try:
        async with asyncio.timeout(EMAIL_WRITING_REVIEW_ROLLBACK_SECONDS):
            await session.rollback()
    except TimeoutError:
        return
    except Exception:
        return


def _validate_context_binding(
    request: EmailWritingReviewRequest,
    bundle: EmailWritingContextBundle,
) -> None:
    """Reject a context/result bound to different request metadata before model use."""
    if (
        bundle.selected_email_id != request.source_email_id
        or bundle.current_draft != request.draft_plain_text
        or bundle.declared_language_tag != request.language_tag
        or bundle.review_mode != request.review_mode
        or bundle.document_revision_digest != request.document_revision.digest_hex
        or bundle.projection_name != request.projection_name
        or bundle.projection_version != request.projection_version
    ):
        raise EmailWritingReviewServiceError("review_revision_stale")


def _validate_candidate_result_binding(
    request: EmailWritingReviewRequest,
    bundle: EmailWritingContextBundle,
    result: EmailWritingCandidateReviewResult,
) -> None:
    """Revalidate injected Candidate metadata, spans, and evidence before Judge use."""
    if result.orchestration_mode != _expected_orchestration_mode(request):
        raise EmailWritingReviewServiceError("candidate_orchestration_mode_invalid")
    if result.output.review_language != request.language_tag:
        raise EmailWritingReviewServiceError("candidate_language_mismatch")
    _validate_candidate_selectors_and_evidence(result.output, bundle)


def _validate_confidence(value: object) -> float:
    """Require an explicitly supplied calibrated confidence mapping before display."""
    if type(value) not in {int, float} or type(value) is bool:
        raise EmailWritingReviewServiceError("review_confidence_unavailable")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise EmailWritingReviewServiceError("review_confidence_unavailable")
    return numeric


class EmailWritingReviewService:
    """Compose the Task 4-8 boundaries into one fail-closed advisory review."""

    def __init__(
        self,
        *,
        candidate_reviewer: EmailWritingReviewCandidatePort | EmailWritingCandidateReviewer,
        independent_judge: EmailWritingReviewJudgePort | EmailWritingIndependentJudge,
        judge_executor: EmailWritingReviewJudgeExecutorPort,
        judge_policy: EmailWritingJudgePolicy,
        runtime_profile: EmailWritingReviewRuntimeProfile,
        context_builder: ContextBuilder = build_email_writing_context,
        policy_evaluator: PolicyEvaluator = evaluate_policy_admission,
        confidence_mapper: ConfidenceMapper | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        """Bind explicit runtime dependencies without resolving providers or secrets."""
        self._candidate_reviewer = candidate_reviewer
        self._independent_judge = independent_judge
        self._judge_executor = judge_executor
        self._judge_policy = judge_policy
        self._runtime_profile = runtime_profile
        self._context_builder = context_builder
        self._policy_evaluator = policy_evaluator
        self._confidence_mapper = confidence_mapper
        self._clock = clock

    async def review(
        self,
        session: AsyncSession | _ReviewEvidenceSession,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
    ) -> EmailWritingReviewResponse:
        """Run one bounded review and persist only final privacy-minimized evidence.

        Editing and sending are outside this service. Every semantic failure is an
        abstention/unavailability state; no local keyword, regex, dictionary, sender,
        recipient, language, or position heuristic manufactures a replacement result.
        """
        if auth_context.organization_id is None:
            raise EmailWritingReviewServiceError("review_owner_scope_unavailable")

        bundle: EmailWritingContextBundle | None = None
        try:
            async with asyncio.timeout(self._runtime_profile.total_wall_seconds):
                bundle = await self._context_builder(session, auth_context, request)
                _validate_context_binding(request, bundle)
                return await self._review_authorized_bundle(
                    session,
                    auth_context,
                    request,
                    bundle,
                )
        except asyncio.CancelledError:
            if bundle is not None:
                evidence_seconds = min(
                    EMAIL_WRITING_REVIEW_TIMEOUT_EVIDENCE_SECONDS,
                    float(self._runtime_profile.total_wall_seconds),
                )
                try:
                    await asyncio.wait_for(
                        self._persist_terminal_review(
                            session,
                            auth_context,
                            request,
                            bundle=bundle,
                            candidate_result=None,
                            review_status="abstained",
                            reason_code="review_cancelled",
                            diagnostics=(),
                        ),
                        timeout=evidence_seconds,
                    )
                except Exception:
                    pass
            raise
        except TimeoutError:
            if bundle is None:
                raise EmailWritingReviewServiceError("review_timeout") from None
            evidence_seconds = min(
                EMAIL_WRITING_REVIEW_TIMEOUT_EVIDENCE_SECONDS,
                float(self._runtime_profile.total_wall_seconds),
            )
            try:
                async with asyncio.timeout(evidence_seconds):
                    return await self._finalize_non_admitted(
                        session,
                        auth_context,
                        request,
                        bundle=bundle,
                        candidate_result=None,
                        review_status="unavailable",
                        reason_code="review_timeout",
                        diagnostics=(),
                    )
            except TimeoutError:
                raise EmailWritingReviewServiceError(
                    "review_evidence_unavailable"
                ) from None
        except EmailWritingContextError as error:
            if error.code == "email_unavailable":
                raise EmailWritingReviewServiceError("email_unavailable") from None
            return await self._finalize_without_bundle_context(
                session,
                auth_context,
                request,
                review_status="context_insufficient",
                reason_code="context_insufficient",
            )
        except EmailWritingReviewServiceError as error:
            if error.code == "review_revision_stale" and bundle is not None:
                return await self._finalize_non_admitted(
                    session,
                    auth_context,
                    request,
                    bundle=bundle,
                    candidate_result=None,
                    review_status="stale",
                    reason_code=error.code,
                    diagnostics=(),
                )
            raise

    async def _review_authorized_bundle(
        self,
        session: AsyncSession | _ReviewEvidenceSession,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
        bundle: EmailWritingContextBundle,
    ) -> EmailWritingReviewResponse:
        """Run Candidate -> Judge -> policy after server authority is established."""
        try:
            candidate_result = await self._candidate_reviewer.review(bundle)
            _validate_candidate_result_binding(request, bundle, candidate_result)
        except EmailWritingCandidateError as error:
            status: ReviewStatus = (
                "rejected"
                if error.code
                in {
                    "candidate_payload_invalid",
                    "candidate_completion_invalid",
                    "candidate_selector_empty",
                    "candidate_selector_out_of_range",
                    "candidate_selector_overlap",
                    "candidate_evidence_unknown",
                }
                else "unavailable"
            )
            return await self._finalize_non_admitted(
                session,
                auth_context,
                request,
                bundle=bundle,
                candidate_result=None,
                review_status=status,
                reason_code=error.code,
                diagnostics=(),
            )
        except EmailWritingReviewServiceError as error:
            return await self._finalize_non_admitted(
                session,
                auth_context,
                request,
                bundle=bundle,
                candidate_result=None,
                review_status="rejected",
                reason_code=error.code,
                diagnostics=(),
            )
        except Exception:
            return await self._finalize_non_admitted(
                session,
                auth_context,
                request,
                bundle=bundle,
                candidate_result=None,
                review_status="unavailable",
                reason_code="provider_unavailable",
                diagnostics=(),
            )

        diagnostics = tuple(candidate_result.output.diagnostics)
        if not diagnostics:
            return await self._finalize_non_admitted(
                session,
                auth_context,
                request,
                bundle=bundle,
                candidate_result=candidate_result,
                review_status="abstained",
                reason_code="candidate_empty",
                diagnostics=(),
            )
        if len(diagnostics) > self._runtime_profile.maximum_candidates:
            return await self._finalize_non_admitted(
                session,
                auth_context,
                request,
                bundle=bundle,
                candidate_result=candidate_result,
                review_status="abstained",
                reason_code="candidate_limit_exceeded",
                diagnostics=diagnostics,
            )

        evaluated: list[_EvaluatedCandidate] = []
        for diagnostic in diagnostics:
            try:
                evaluation = await self._judge_executor.run_judge(
                    self._independent_judge.evaluate,
                    diagnostic,
                    bundle,
                    candidate_model_profile_id=(
                        self._runtime_profile.candidate_model_profile_id
                    ),
                    judge_model_profile_id=self._runtime_profile.judge_model_profile_id,
                    category_count=self._judge_policy.category_count,
                    category_anchors=tuple(self._judge_policy.category_anchors),
                )
            except EmailWritingJudgeError as error:
                return await self._finalize_non_admitted(
                    session,
                    auth_context,
                    request,
                    bundle=bundle,
                    candidate_result=candidate_result,
                    review_status="abstained",
                    reason_code=error.code,
                    diagnostics=diagnostics,
                    successful_evaluations=evaluated,
                )
            except Exception:
                return await self._finalize_non_admitted(
                    session,
                    auth_context,
                    request,
                    bundle=bundle,
                    candidate_result=candidate_result,
                    review_status="abstained",
                    reason_code="judge_runner_failed",
                    diagnostics=diagnostics,
                    successful_evaluations=evaluated,
                )

            try:
                outcome = self._policy_evaluator(
                    policy=self._judge_policy,
                    language_tag=request.language_tag,
                    review_mode=request.review_mode,
                    candidate_model_profile_id=(
                        self._runtime_profile.candidate_model_profile_id
                    ),
                    candidate_provider_id=self._runtime_profile.candidate_provider_id,
                    judge_model_profile_id=self._runtime_profile.judge_model_profile_id,
                    judge_provider_id=self._runtime_profile.judge_provider_id,
                    rubric_version=self._runtime_profile.rubric_version,
                    criterion_categories=evaluation.criterion_categories,
                    criterion_scores=evaluation.criterion_scores,
                    candidate_kind=_candidate_kind(diagnostic),
                )
            except EmailWritingPolicyError:
                return await self._finalize_non_admitted(
                    session,
                    auth_context,
                    request,
                    bundle=bundle,
                    candidate_result=candidate_result,
                    review_status="unavailable",
                    reason_code="policy_validation_failed",
                    diagnostics=diagnostics,
                    successful_evaluations=evaluated,
                )
            except Exception:
                return await self._finalize_non_admitted(
                    session,
                    auth_context,
                    request,
                    bundle=bundle,
                    candidate_result=candidate_result,
                    review_status="unavailable",
                    reason_code="policy_unavailable",
                    diagnostics=diagnostics,
                    successful_evaluations=evaluated,
                )

            evaluated.append(
                _EvaluatedCandidate(
                    diagnostic=diagnostic,
                    evaluation=evaluation,
                    outcome=outcome,
                    diagnostic_identifier=str(uuid.uuid4()),
                )
            )

            if outcome != "admit":
                status, reason_code = self._status_for_policy_outcome(outcome)
                return await self._finalize_non_admitted(
                    session,
                    auth_context,
                    request,
                    bundle=bundle,
                    candidate_result=candidate_result,
                    review_status=status,
                    reason_code=reason_code,
                    diagnostics=diagnostics,
                    successful_evaluations=evaluated,
                )

        if self._confidence_mapper is None:
            return await self._finalize_non_admitted(
                session,
                auth_context,
                request,
                bundle=bundle,
                candidate_result=candidate_result,
                review_status="unavailable",
                reason_code="review_confidence_unavailable",
                diagnostics=diagnostics,
                successful_evaluations=evaluated,
            )

        response_diagnostics: list[EmailWritingDiagnostic] = []
        persistence_diagnostics: list[_PersistenceDiagnostic] = []
        provenance = self._provenance(request, candidate_result)
        for item in evaluated:
            confidence = _validate_confidence(self._confidence_mapper(item.evaluation))
            response_diagnostics.append(
                EmailWritingDiagnostic(
                    diagnostic_id=item.diagnostic_identifier,
                    document_revision=request.document_revision,
                    projection_name=request.projection_name,
                    projection_version=request.projection_version,
                    selector=item.diagnostic.selector,
                    category_code=item.diagnostic.category_code,
                    priority=item.diagnostic.priority,
                    title=item.diagnostic.title,
                    explanation=item.diagnostic.explanation,
                    suggested_replacement=item.diagnostic.suggested_replacement,
                    confidence=confidence,
                    provenance=provenance,
                )
            )
            persistence_diagnostics.append(
                _PersistenceDiagnostic(
                    diagnostic=item.diagnostic,
                    evaluation=item.evaluation,
                    diagnostic_identifier=item.diagnostic_identifier,
                    admission_status="admitted",
                    admission_reason_code="policy_admit",
                )
            )

        review_session_id = await self._persist_review(
            session,
            auth_context,
            request,
            candidate_result=candidate_result,
            review_status="completed",
            diagnostics=tuple(persistence_diagnostics),
        )
        return EmailWritingReviewResponse(
            review_session_id=review_session_id,
            document_revision=request.document_revision,
            projection_name=request.projection_name,
            projection_version=request.projection_version,
            review_status="completed",
            diagnostics=response_diagnostics,
            document_guidance=candidate_result.output.document_guidance,
            context_limitations=_stable_unique(
                [
                    *bundle.context_limitations,
                    *candidate_result.output.context_limitations,
                ]
            ),
            abstained_claims=_stable_unique(
                list(candidate_result.output.abstained_claims)
            ),
            provenance=provenance,
        )

    @staticmethod
    def _status_for_policy_outcome(outcome: AdmissionOutcome) -> tuple[ReviewStatus, str]:
        """Map structured admission states without inspecting authored content."""
        if outcome == "adjudicate":
            return "judge_disagreement", "policy_adjudication_required"
        if outcome == "policy_unavailable":
            return "unavailable", "policy_unavailable"
        if outcome == "unsupported_profile":
            return "abstained", "unsupported_profile"
        return "abstained", "policy_withhold"

    def _provenance(
        self,
        request: EmailWritingReviewRequest,
        candidate_result: EmailWritingCandidateReviewResult | None,
    ) -> EmailWritingProvenance:
        """Build browser-safe workflow provenance without raw model/provider content."""
        return EmailWritingProvenance(
            workflow_id=self._runtime_profile.workflow_identifier,
            workflow_version=self._runtime_profile.workflow_version,
            judge_policy_version=self._judge_policy.policy_version,
            rubric_version=self._runtime_profile.rubric_version,
            model_profile_id=self._runtime_profile.candidate_model_profile_id,
            orchestration_mode=(
                candidate_result.orchestration_mode
                if candidate_result is not None
                else _expected_orchestration_mode(request)
            ),
            prompt_hash=(
                candidate_result.prompt_hash
                if candidate_result is not None
                else _EMPTY_PROMPT_HASH
            ),
        )

    async def _finalize_without_bundle_context(
        self,
        session: AsyncSession | _ReviewEvidenceSession,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
        *,
        review_status: ReviewStatus,
        reason_code: str,
    ) -> EmailWritingReviewResponse:
        """Persist an authorized selected-email failure without claiming model context."""
        review_session_id = await self._persist_review(
            session,
            auth_context,
            request,
            candidate_result=None,
            review_status=review_status,
            diagnostics=(),
        )
        return self._empty_response(
            request,
            review_session_id=review_session_id,
            review_status=review_status,
            reason_code=reason_code,
            context_limitations=(),
        )

    async def _finalize_non_admitted(
        self,
        session: AsyncSession | _ReviewEvidenceSession,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
        *,
        bundle: EmailWritingContextBundle,
        candidate_result: EmailWritingCandidateReviewResult | None,
        review_status: ReviewStatus,
        reason_code: str,
        diagnostics: tuple[EmailWritingCandidateDiagnostic, ...],
        successful_evaluations: list[_EvaluatedCandidate] | None = None,
    ) -> EmailWritingReviewResponse:
        """Atomically withhold every Candidate when any review lane cannot admit."""
        evaluated_by_identity: dict[int, _EvaluatedCandidate] = {
            id(item.diagnostic): item for item in (successful_evaluations or [])
        }
        persistence_diagnostics: list[_PersistenceDiagnostic] = []
        for diagnostic in diagnostics:
            existing = evaluated_by_identity.get(id(diagnostic))
            persistence_diagnostics.append(
                _PersistenceDiagnostic(
                    diagnostic=diagnostic,
                    evaluation=existing.evaluation if existing is not None else None,
                    diagnostic_identifier=(
                        existing.diagnostic_identifier
                        if existing is not None
                        else str(uuid.uuid4())
                    ),
                    admission_status="abstained",
                    admission_reason_code=reason_code,
                )
            )

        review_session_id = await self._persist_review(
            session,
            auth_context,
            request,
            candidate_result=candidate_result,
            review_status=review_status,
            diagnostics=tuple(persistence_diagnostics),
        )
        context_limitations = list(bundle.context_limitations)
        if candidate_result is not None:
            context_limitations.extend(candidate_result.output.context_limitations)
        return self._empty_response(
            request,
            review_session_id=review_session_id,
            review_status=review_status,
            reason_code=reason_code,
            context_limitations=tuple(_stable_unique(context_limitations)),
            candidate_result=candidate_result,
        )

    async def _persist_terminal_review(
        self,
        session: AsyncSession | _ReviewEvidenceSession,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
        *,
        bundle: EmailWritingContextBundle,
        candidate_result: EmailWritingCandidateReviewResult | None,
        review_status: ReviewStatus,
        reason_code: str,
        diagnostics: tuple[EmailWritingCandidateDiagnostic, ...],
    ) -> str:
        """Persist cancellation/terminal state without returning semantic content."""
        del bundle, reason_code
        persistence_diagnostics = tuple(
            _PersistenceDiagnostic(
                diagnostic=diagnostic,
                evaluation=None,
                diagnostic_identifier=str(uuid.uuid4()),
                admission_status="abstained",
                admission_reason_code="review_cancelled",
            )
            for diagnostic in diagnostics
        )
        return await self._persist_review(
            session,
            auth_context,
            request,
            candidate_result=candidate_result,
            review_status=review_status,
            diagnostics=persistence_diagnostics,
        )

    def _empty_response(
        self,
        request: EmailWritingReviewRequest,
        *,
        review_session_id: str,
        review_status: ReviewStatus,
        reason_code: str,
        context_limitations: tuple[str, ...],
        candidate_result: EmailWritingCandidateReviewResult | None = None,
    ) -> EmailWritingReviewResponse:
        """Return status-only evidence with no unjudged semantic Candidate content."""
        return EmailWritingReviewResponse(
            review_session_id=review_session_id,
            document_revision=request.document_revision,
            projection_name=request.projection_name,
            projection_version=request.projection_version,
            review_status=review_status,
            diagnostics=[],
            document_guidance=_empty_document_guidance(),
            context_limitations=list(context_limitations),
            abstained_claims=[reason_code],
            provenance=self._provenance(request, candidate_result),
        )

    async def _persist_review(
        self,
        session: AsyncSession | _ReviewEvidenceSession,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
        *,
        candidate_result: EmailWritingCandidateReviewResult | None,
        review_status: ReviewStatus,
        diagnostics: tuple[_PersistenceDiagnostic, ...],
    ) -> str:
        """Commit one minimized review aggregate or fail without returning diagnostics."""
        organization_id = auth_context.organization_id
        if organization_id is None:
            raise EmailWritingReviewServiceError("review_owner_scope_unavailable")
        created_at = self._clock()
        if created_at.tzinfo is None:
            raise EmailWritingReviewServiceError("review_clock_invalid")
        created_at = created_at.astimezone(datetime.timezone.utc)
        review_session_id = str(uuid.uuid4())
        review_record = EmailReviewSession(
            review_session_id=review_session_id,
            owner_user_id=auth_context.user_id,
            owner_organization_id=organization_id,
            source_email_id=request.source_email_id,
            revision_algorithm=request.document_revision.algorithm,
            revision_digest=request.document_revision.digest_hex,
            revision_entity_tag=request.document_revision.strong_entity_tag,
            projection_name=request.projection_name,
            projection_version=request.projection_version,
            review_mode=request.review_mode,
            language_profile=request.language_tag,
            review_status=review_status,
            workflow_identifier=self._runtime_profile.workflow_identifier,
            workflow_version=self._runtime_profile.workflow_version,
            model_profile_id=self._runtime_profile.candidate_model_profile_id,
            rubric_version=self._runtime_profile.rubric_version,
            judge_policy_version=self._judge_policy.policy_version,
            orchestration_mode=(
                candidate_result.orchestration_mode
                if candidate_result is not None
                else _expected_orchestration_mode(request)
            ),
            prompt_hash=(
                candidate_result.prompt_hash
                if candidate_result is not None
                else _EMPTY_PROMPT_HASH
            ),
            latency_bucket_ms=0,
            cost_bucket_micro_usd=0,
            prompt_token_bucket=0,
            completion_token_bucket=0,
            created_at=created_at,
            evidence_expires_at=(
                created_at
                + datetime.timedelta(days=EMAIL_WRITING_REVIEW_RETENTION_DAYS)
            ),
        )

        for item in diagnostics:
            candidate_payload: Mapping[str, Any] = item.diagnostic.model_dump(mode="json")
            review_record.writing_diagnostic_records.append(
                WritingDiagnosticRecord(
                    diagnostic_identifier=item.diagnostic_identifier,
                    diagnostic_category=item.diagnostic.category_code,
                    diagnostic_priority=item.diagnostic.priority,
                    selector_start=item.diagnostic.selector.start,
                    selector_end=item.diagnostic.selector.end,
                    candidate_hash=_sha256_json(candidate_payload),
                    replacement_hash=(
                        _sha256_text(item.diagnostic.suggested_replacement)
                        if item.diagnostic.suggested_replacement is not None
                        else None
                    ),
                    explanation_hash=_sha256_text(item.diagnostic.explanation),
                    criterion_categories_json=_criterion_category_receipt(
                        item.evaluation
                    ),
                    judge_score=_overall_judge_score(item.evaluation),
                    admission_status=item.admission_status,
                    admission_reason_code=item.admission_reason_code,
                    created_at=created_at,
                )
            )

        session.add(review_record)
        try:
            await session.commit()
        except asyncio.CancelledError:
            await _rollback_bounded(session)
            raise
        except Exception:
            await _rollback_bounded(session)
            raise EmailWritingReviewServiceError("review_evidence_unavailable") from None
        return review_session_id
