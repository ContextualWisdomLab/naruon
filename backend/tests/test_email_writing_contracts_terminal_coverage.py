"""Terminal branch coverage for strict email-writing transport validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.email_writing_contracts import (
    EmailWritingDiagnostic,
    EmailWritingProvenance,
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


def test_provenance_rejects_a_non_sha256_prompt_hash() -> None:
    """The public contract accepts only a redacted SHA-256 prompt digest."""
    invalid = {**PROVENANCE, "prompt_hash": "sha256:not-a-digest"}

    with pytest.raises(ValidationError, match="prompt_hash_invalid"):
        EmailWritingProvenance.model_validate(invalid)


def test_diagnostic_rejects_an_invalid_category_code() -> None:
    """Category identifiers fail closed instead of accepting free-form text."""
    invalid = {
        "diagnostic_id": "coverage_diagnostic",
        "document_revision": REVISION,
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "selector": {
            "type": "TextPositionSelector",
            "start": 0,
            "end": 5,
        },
        "category_code": "Invalid Category",
        "priority": "advisory",
        "title": "Clarify the action",
        "explanation": "State the requested action explicitly.",
        "suggested_replacement": None,
        "confidence": 0.5,
        "provenance": PROVENANCE,
    }

    with pytest.raises(ValidationError, match="category_code_invalid"):
        EmailWritingDiagnostic.model_validate(invalid)
