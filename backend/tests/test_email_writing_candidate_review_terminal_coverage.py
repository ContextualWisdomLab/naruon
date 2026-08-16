"""Terminal branch-coverage tests for email-writing candidate validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.email_writing_candidate_review import EmailWritingCandidateDiagnostic


def _diagnostic(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "selector": {
            "type": "TextPositionSelector",
            "start": 0,
            "end": 1,
        },
        "category_code": "clarity",
        "priority": "advisory",
        "title": "Clarify the request",
        "explanation": "The requested next action is not explicit.",
        "suggested_replacement": "Please confirm the next action.",
        "candidate_confidence": 0.8,
        "candidate_evidence_ids": ["draft"],
    }
    value.update(overrides)
    return value


def test_candidate_title_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        EmailWritingCandidateDiagnostic.model_validate(
            _diagnostic(title="x" * 513)
        )


def test_candidate_explanation_rejects_non_scalar_unicode() -> None:
    with pytest.raises(ValidationError):
        EmailWritingCandidateDiagnostic.model_validate(
            _diagnostic(explanation="unsafe\ud800text")
        )


def test_candidate_replacement_may_be_omitted() -> None:
    diagnostic = EmailWritingCandidateDiagnostic.model_validate(
        _diagnostic(suggested_replacement=None)
    )
    assert diagnostic.suggested_replacement is None


def test_candidate_evidence_identifier_grammar_is_fail_closed() -> None:
    with pytest.raises(ValidationError):
        EmailWritingCandidateDiagnostic.model_validate(
            _diagnostic(candidate_evidence_ids=["email/not-an-id"])
        )
