"""Branch-complete tests for strict email-writing transport validation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from services.email_writing_contracts import (
    MAX_JSON_BYTES,
    EmailWritingDiagnostic,
    EmailWritingDocumentGuidance,
    EmailWritingReviewRequest,
    EmailWritingReviewResponse,
    StrictEmailWritingJsonError,
    parse_strict_email_writing_json,
)

DIGEST = "7c" * 32
REVISION = {
    "algorithm": "SHA-256",
    "digest_hex": DIGEST,
    "strong_entity_tag": f'"sha256-{DIGEST}"',
}
PROVENANCE = {
    "workflow_id": "email_writing_review",
    "workflow_version": "1",
    "judge_policy_version": "evaluation_only_v1",
    "rubric_version": "email_writing_rubric_v1",
    "model_profile_id": "review_profile_v1",
    "orchestration_mode": "route",
    "prompt_hash": "sha256:" + "ab" * 32,
}


def request_payload() -> dict[str, object]:
    """Return one valid incremental request for boundary mutation."""
    return {
        "source_email_id": 1,
        "document_revision": REVISION,
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "draft_plain_text": "Alpha beta gamma",
        "language_tag": "en-US",
        "review_mode": "incremental",
        "changed_selector": {
            "type": "TextPositionSelector",
            "start": 0,
            "end": 5,
        },
        "reply_objective": None,
    }


def diagnostic_payload() -> dict[str, object]:
    """Return one valid diagnostic for boundary mutation."""
    return {
        "diagnostic_id": "coverage_diagnostic",
        "document_revision": REVISION,
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "selector": {
            "type": "TextPositionSelector",
            "start": 0,
            "end": 5,
        },
        "category_code": "clarity",
        "priority": "advisory",
        "title": "Clarify the action",
        "explanation": "State the requested action explicitly.",
        "suggested_replacement": None,
        "confidence": 0.0,
        "provenance": PROVENANCE,
    }


def response_payload() -> dict[str, object]:
    """Return one valid response for strict raw-JSON parsing."""
    return {
        "review_session_id": "email_review_coverage",
        "document_revision": REVISION,
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "review_status": "abstained",
        "diagnostics": [diagnostic_payload()],
        "document_guidance": {
            "purpose_summary": "",
            "reader_interpretation": "",
            "missing_requests": [],
            "structure_suggestion": "",
        },
        "context_limitations": [],
        "abstained_claims": [],
        "provenance": PROVENANCE,
    }


def test_request_boundary_failures_are_deterministic() -> None:
    """Positive identifiers, language tags, and selector bounds fail closed."""
    invalid_id = request_payload()
    invalid_id["source_email_id"] = 0
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(invalid_id)

    for language_tag in ("", "x", "en--US", "en_US", "9-en", "a" * 64):
        invalid_language = request_payload()
        invalid_language["language_tag"] = language_tag
        with pytest.raises(ValidationError):
            EmailWritingReviewRequest.model_validate(invalid_language)

    out_of_range = request_payload()
    out_of_range["changed_selector"] = {
        "type": "TextPositionSelector",
        "start": 0,
        "end": len(str(out_of_range["draft_plain_text"])) + 1,
    }
    with pytest.raises(ValidationError):
        EmailWritingReviewRequest.model_validate(out_of_range)


def test_identifier_replacement_and_guidance_boundaries_are_covered() -> None:
    """Opaque identifiers and inert response text remain strictly bounded."""
    for diagnostic_id in ("", "bad/id", "x" * 129, " bad"):
        invalid = diagnostic_payload()
        invalid["diagnostic_id"] = diagnostic_id
        with pytest.raises(ValidationError):
            EmailWritingDiagnostic.model_validate(invalid)

    valid_absent = diagnostic_payload()
    valid_absent.pop("suggested_replacement")
    assert (
        EmailWritingDiagnostic.model_validate(valid_absent).suggested_replacement
        is None
    )

    invalid_replacement = diagnostic_payload()
    invalid_replacement["suggested_replacement"] = "x" * 20_001
    with pytest.raises(ValidationError):
        EmailWritingDiagnostic.model_validate(invalid_replacement)

    for missing_requests in ([""], ["x" * 1_025]):
        with pytest.raises(ValidationError):
            EmailWritingDocumentGuidance.model_validate(
                {
                    "purpose_summary": "purpose",
                    "reader_interpretation": "reader",
                    "missing_requests": missing_requests,
                    "structure_suggestion": "structure",
                }
            )


def test_strict_parser_accepts_valid_utf8_bytes_and_rejects_bad_sources() -> None:
    """Both text and byte inputs enforce UTF-8, payload, and source-type limits."""
    encoded = json.dumps(response_payload(), ensure_ascii=False).encode("utf-8")
    parsed = parse_strict_email_writing_json(encoded, EmailWritingReviewResponse)
    assert parsed.review_session_id == "email_review_coverage"

    with pytest.raises(StrictEmailWritingJsonError, match="invalid_unicode"):
        parse_strict_email_writing_json(b"\xff", EmailWritingReviewResponse)

    with pytest.raises(StrictEmailWritingJsonError, match="payload_limit"):
        parse_strict_email_writing_json(
            b"x" * (MAX_JSON_BYTES + 1),
            EmailWritingReviewResponse,
        )

    with pytest.raises(StrictEmailWritingJsonError, match="invalid_unicode"):
        parse_strict_email_writing_json("\ud800", EmailWritingReviewResponse)

    with pytest.raises(StrictEmailWritingJsonError, match="source_type"):
        parse_strict_email_writing_json(7, EmailWritingReviewResponse)  # type: ignore[arg-type]


def test_strict_parser_exercises_shape_and_invalid_json_limits() -> None:
    """Parsed JSON is bounded by shape before Pydantic receives it."""
    with pytest.raises(StrictEmailWritingJsonError, match="invalid_json"):
        parse_strict_email_writing_json("{", EmailWritingReviewResponse)

    with pytest.raises(StrictEmailWritingJsonError, match="object_limit"):
        parse_strict_email_writing_json(
            json.dumps({f"key_{index}": 0 for index in range(1_001)}),
            EmailWritingReviewResponse,
        )

    node_heavy = {
        "items": [[0 for _ in range(20)] for _ in range(1_000)],
    }
    with pytest.raises(StrictEmailWritingJsonError, match="node_limit"):
        parse_strict_email_writing_json(
            json.dumps(node_heavy),
            EmailWritingReviewResponse,
        )

    escaped_surrogate = json.dumps({"bad": "\ud800"})
    with pytest.raises(StrictEmailWritingJsonError, match="invalid_unicode"):
        parse_strict_email_writing_json(
            escaped_surrogate,
            EmailWritingReviewResponse,
        )


def test_strict_parser_covers_empty_containers_before_model_validation() -> None:
    """Empty parsed containers reach the exact model validator without repair."""
    with pytest.raises(ValidationError):
        parse_strict_email_writing_json("{}", EmailWritingReviewResponse)
    with pytest.raises(ValidationError):
        parse_strict_email_writing_json("[]", EmailWritingReviewResponse)
