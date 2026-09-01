"""Contract tests for the LLM-native email writing review transport boundary."""

from __future__ import annotations

import json
import math

import pytest
from pydantic import ValidationError

from services.email_writing_contracts import (
    EmailWritingDiagnostic,
    EmailWritingDocumentGuidance,
    EmailWritingDocumentRevision,
    EmailWritingFeedbackRequest,
    EmailWritingReviewRequest,
    EmailWritingReviewResponse,
    EmailWritingTextPositionSelector,
    StrictEmailWritingJsonError,
    parse_strict_email_writing_json,
)

DIGEST = "4a" * 32
REVISION = {
    "algorithm": "SHA-256",
    "digest_hex": DIGEST,
    "strong_entity_tag": f'"sha256-{DIGEST}"',
}
PROJECTION = {
    "projection_name": "inkspan-prosemirror-text",
    "projection_version": 1,
}


def valid_incremental_request() -> dict[str, object]:
    """Return one valid incremental review request fixture."""
    return {
        "source_email_id": 184,
        "document_revision": REVISION,
        **PROJECTION,
        "draft_plain_text": "안녕하세요. 수행 주체와 회신 일정을 확인 부탁드립니다.",
        "language_tag": "ko-KR",
        "review_mode": "incremental",
        "changed_selector": {
            "type": "TextPositionSelector",
            "start": 0,
            "end": 12,
        },
        "reply_objective": "수행 범위와 회신 일정을 확인",
    }


def valid_diagnostic(diagnostic_id: str = "writing_diagnostic_01") -> dict[str, object]:
    """Return one valid admitted diagnostic fixture."""
    return {
        "diagnostic_id": diagnostic_id,
        "document_revision": REVISION,
        **PROJECTION,
        "selector": {
            "type": "TextPositionSelector",
            "start": 7,
            "end": 12,
        },
        "category_code": "audience_pragmatics",
        "priority": "important",
        "title": "질문의 목적을 먼저 제시하세요",
        "explanation": "현재 문장은 확인 요청보다 답변을 평가하는 반문으로 읽힐 수 있습니다.",
        "suggested_replacement": "말씀하신 작업의 수행 주체와 범위를 확인 부탁드립니다.",
        "confidence": 0.86,
        "provenance": {
            "workflow_id": "email_writing_review",
            "workflow_version": "1",
            "judge_policy_version": "evaluation_only_v1",
            "rubric_version": "email_writing_rubric_v1",
            "model_profile_id": "review_profile_v1",
            "orchestration_mode": "conduct",
            "prompt_hash": "sha256:" + "ab" * 32,
        },
    }


def valid_response() -> dict[str, object]:
    """Return one valid review response fixture."""
    return {
        "review_session_id": "email_review_01JTEST",
        "document_revision": REVISION,
        **PROJECTION,
        "review_status": "completed",
        "diagnostics": [valid_diagnostic()],
        "document_guidance": {
            "purpose_summary": "수행 범위와 일정 확인",
            "reader_interpretation": "핵심 요청과 전문성 방어가 섞일 수 있음",
            "missing_requests": ["수행 주체", "회신 가능 예정일"],
            "structure_suggestion": "목적, 확인 항목, 일정 순으로 정리",
        },
        "context_limitations": [],
        "abstained_claims": [],
        "provenance": {
            "workflow_id": "email_writing_review",
            "workflow_version": "1",
            "judge_policy_version": "evaluation_only_v1",
            "rubric_version": "email_writing_rubric_v1",
            "model_profile_id": "review_profile_v1",
            "orchestration_mode": "conduct",
            "prompt_hash": "sha256:" + "ab" * 32,
        },
    }


def test_incremental_and_deep_request_contracts_are_exact() -> None:
    """Incremental requires a selector while deep review forbids one."""
    request = EmailWritingReviewRequest.model_validate(valid_incremental_request())
    assert request.changed_selector is not None
    assert request.document_revision.digest_hex == DIGEST

    deep = valid_incremental_request()
    deep["review_mode"] = "deep"
    deep["changed_selector"] = None
    assert EmailWritingReviewRequest.model_validate(deep).changed_selector is None

    missing = valid_incremental_request()
    missing["changed_selector"] = None
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(missing)

    illegal = valid_incremental_request()
    illegal["review_mode"] = "deep"
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(illegal)

    extra = valid_incremental_request()
    extra["recipient_count"] = 8
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(extra)


def test_request_rejects_invalid_projection_language_bounds_and_unicode() -> None:
    """Transport syntax and resource bounds fail closed before semantic review."""
    bad_projection = valid_incremental_request()
    bad_projection["projection_name"] = "nearest-text"
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(bad_projection)

    bad_version = valid_incremental_request()
    bad_version["projection_version"] = 2
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(bad_version)

    for language_tag in ("k", "ko--KR", "ko_kr", "123", "ko-💥"):
        payload = valid_incremental_request()
        payload["language_tag"] = language_tag
        with pytest.raises(ValidationError):
            EmailWritingReviewRequest.model_validate(payload)

    out_of_range = valid_incremental_request()
    out_of_range["changed_selector"] = {
        "type": "TextPositionSelector",
        "start": 0,
        "end": 10_000,
    }
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(out_of_range)

    surrogate = valid_incremental_request()
    surrogate["draft_plain_text"] = "unsafe\ud800text"
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(surrogate)

    oversized = valid_incremental_request()
    oversized["draft_plain_text"] = "가" * 200_001
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(oversized)

    oversized_objective = valid_incremental_request()
    oversized_objective["reply_objective"] = "x" * 4_001
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(oversized_objective)


def test_revision_and_selector_are_strict_and_js_safe() -> None:
    """Strong revision and selector values cannot be repaired or coerced."""
    assert EmailWritingDocumentRevision.model_validate(REVISION).strong_entity_tag == (
        f'"sha256-{DIGEST}"'
    )

    for revision in (
        {**REVISION, "algorithm": "SHA-1"},
        {**REVISION, "digest_hex": "AB" * 32},
        {**REVISION, "digest_hex": "00"},
        {**REVISION, "strong_entity_tag": f'W/"sha256-{DIGEST}"'},
        {**REVISION, "strong_entity_tag": f'"sha256-{"00" * 32}"'},
        {**REVISION, "provider_url": "https://secret.example"},
    ):
        with pytest.raises(ValidationError):
            EmailWritingDocumentRevision.model_validate(revision)

    for selector in (
        {"type": "TextPositionSelector", "start": 0.0, "end": 1},
        {"type": "TextPositionSelector", "start": True, "end": 1},
        {"type": "TextPositionSelector", "start": -1, "end": 1},
        {"type": "TextPositionSelector", "start": 2, "end": 1},
        {"type": "TextPositionSelector", "start": 0, "end": 2**53},
        {"type": "TextQuoteSelector", "start": 0, "end": 1},
    ):
        with pytest.raises(ValidationError):
            EmailWritingTextPositionSelector.model_validate(selector)


def test_response_rejects_duplicates_invalid_enums_and_non_finite_values() -> None:
    """Only exact, bounded and non-duplicated diagnostics reach the editor adapter."""
    response = EmailWritingReviewResponse.model_validate(valid_response())
    assert response.review_status == "completed"
    assert response.diagnostics[0].diagnostic_id == "writing_diagnostic_01"

    duplicate = valid_response()
    duplicate["diagnostics"] = [valid_diagnostic("same"), valid_diagnostic("same")]
    with pytest.raises(ValidationError):
        EmailWritingReviewResponse.model_validate(duplicate)

    invalid_status = valid_response()
    invalid_status["review_status"] = "safe_to_send"
    with pytest.raises(ValidationError):
        EmailWritingReviewResponse.model_validate(invalid_status)

    invalid_priority = valid_diagnostic()
    invalid_priority["priority"] = "danger"
    with pytest.raises(ValidationError):
        EmailWritingDiagnostic.model_validate(invalid_priority)

    invalid_confidence = valid_diagnostic()
    invalid_confidence["confidence"] = math.nan
    with pytest.raises(ValidationError):
        EmailWritingDiagnostic.model_validate(invalid_confidence)

    too_many = valid_response()
    too_many["diagnostics"] = [
        valid_diagnostic(f"diag_{index}") for index in range(65)
    ]
    with pytest.raises(ValidationError):
        EmailWritingReviewResponse.model_validate(too_many)


def test_guidance_and_feedback_are_bounded_and_action_exact() -> None:
    """Guidance is non-mutating and feedback exposes only the approved action enum."""
    guidance = EmailWritingDocumentGuidance.model_validate(
        valid_response()["document_guidance"]
    )
    assert guidance.missing_requests == ["수행 주체", "회신 가능 예정일"]

    feedback = EmailWritingFeedbackRequest.model_validate(
        {
            "diagnostic_id": "writing_diagnostic_01",
            "document_revision": REVISION,
            "feedback_action": "applied",
            "resulting_document_revision": {
                **REVISION,
                "digest_hex": "5b" * 32,
                "strong_entity_tag": f'"sha256-{"5b" * 32}"',
            },
        }
    )
    assert feedback.feedback_action == "applied"

    for action in (
        "ignored",
        "dismissed",
        "requested_explanation",
        "stale",
        "conflict",
    ):
        payload = {
            "diagnostic_id": "writing_diagnostic_01",
            "document_revision": REVISION,
            "feedback_action": action,
        }
        assert EmailWritingFeedbackRequest.model_validate(payload).feedback_action == action

    missing_result = {
        "diagnostic_id": "writing_diagnostic_01",
        "document_revision": REVISION,
        "feedback_action": "applied",
    }
    with pytest.raises(ValidationError):
        EmailWritingFeedbackRequest.model_validate(missing_result)

    illegal_result = {
        "diagnostic_id": "writing_diagnostic_01",
        "document_revision": REVISION,
        "feedback_action": "ignored",
        "resulting_document_revision": REVISION,
    }
    with pytest.raises(ValidationError):
        EmailWritingFeedbackRequest.model_validate(illegal_result)

    unsafe_action = {
        "diagnostic_id": "writing_diagnostic_01",
        "document_revision": REVISION,
        "feedback_action": "send_anyway",
    }
    with pytest.raises(ValidationError):
        EmailWritingFeedbackRequest.model_validate(unsafe_action)


def test_strict_json_parser_rejects_duplicate_keys_depth_size_and_constants() -> None:
    """Raw model/API JSON cannot exploit ordinary json.loads permissiveness."""
    raw = json.dumps(valid_response(), ensure_ascii=False)
    parsed = parse_strict_email_writing_json(raw, EmailWritingReviewResponse)
    assert parsed.review_session_id == "email_review_01JTEST"

    with pytest.raises(StrictEmailWritingJsonError, match="duplicate_key"):
        parse_strict_email_writing_json(
            '{"source_email_id":1,"source_email_id":2}',
            EmailWritingReviewRequest,
        )

    with pytest.raises(StrictEmailWritingJsonError, match="non_finite_number"):
        parse_strict_email_writing_json('{"confidence":NaN}', EmailWritingDiagnostic)

    deeply_nested: object = "leaf"
    for _ in range(20):
        deeply_nested = {"nested": deeply_nested}
    with pytest.raises(StrictEmailWritingJsonError, match="nesting_limit"):
        parse_strict_email_writing_json(
            json.dumps(deeply_nested),
            EmailWritingReviewResponse,
        )

    huge_array = {"diagnostics": [{} for _ in range(1_001)]}
    with pytest.raises(StrictEmailWritingJsonError, match="array_limit"):
        parse_strict_email_writing_json(
            json.dumps(huge_array),
            EmailWritingReviewResponse,
        )

    with pytest.raises(StrictEmailWritingJsonError, match="payload_limit"):
        parse_strict_email_writing_json(
            '"' + ("x" * 1_100_000) + '"',
            EmailWritingReviewResponse,
        )
