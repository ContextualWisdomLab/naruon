"""Regression for fail-closed Task 8 candidate-kind admission."""

import pytest

from services.email_writing_policy import (
    EmailWritingPolicyError,
    evaluate_policy_admission,
)
from tests.test_email_writing_policy import (
    _REQUIRED_CRITERIA,
    _load,
    _published_policy,
)

_RUNTIME_CONTRACTS = {
    "naruon": "0.14.4",
    "inkspan": "0.6.0",
    "fast_mlsirm": "0.9.2",
    "contextual_orchestrator": "v1",
}


def test_unknown_candidate_kind_fails_with_stable_policy_error() -> None:
    """Untrusted candidate-kind input must not escape as a raw mapping KeyError."""
    policy = _load(_published_policy(), runtime_contracts=_RUNTIME_CONTRACTS)

    with pytest.raises(EmailWritingPolicyError, match="candidate_kind_invalid"):
        evaluate_policy_admission(
            policy=policy,
            language_tag="en",
            review_mode="deep",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="independent-judge-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            criterion_categories={criterion: 3 for criterion in _REQUIRED_CRITERIA},
            criterion_scores={criterion: 1.0 for criterion in _REQUIRED_CRITERIA},
            candidate_kind="unknown_candidate_kind",
        )
