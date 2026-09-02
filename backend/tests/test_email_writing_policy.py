"""Regression contract for versioned email-writing Judge admission policy."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from services.email_writing_policy import (
    EmailWritingPolicyError,
    evaluate_policy_admission,
    load_policy_artifact,
    select_rollback_policy,
)

_POLICY_DIR = Path(__file__).resolve().parents[1] / "policies"
_POLICY_NAME = "email_writing_judge_evaluation_only_v1.json"
_NOW = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
_RUNTIME_CONTRACTS = {
    "naruon": "0.14.4",
    "inkspan": None,
    "fast_mlsirm": None,
    "contextual_orchestrator": "v1",
}
_REQUIRED_CRITERIA = (
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


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    """Serialize an artifact exactly as the integrity manifest contract expects."""
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _manifest_for(name: str, payload: dict[str, object]) -> dict[str, object]:
    """Build a minimal manifest bound to one canonical test artifact."""
    digest = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return {
        "manifest_version": 1,
        "artifacts": {name: {"sha256": digest}},
    }


def _evaluation_policy() -> dict[str, object]:
    """Return the checked-in evaluation policy as mutable test data."""
    return json.loads((_POLICY_DIR / _POLICY_NAME).read_text(encoding="utf-8"))


def _published_policy(*, version: str = "email-writing-policy-v1") -> dict[str, object]:
    """Build a fully evidenced synthetic published policy for deterministic tests."""
    payload = _evaluation_policy()
    payload.update(
        {
            "policy_id": "email_writing_judge_policy",
            "policy_version": version,
            "status": "published",
            "publish_decision": "publish",
            "compatible_contracts": {
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.2",
                "contextual_orchestrator": "v1",
            },
            "calibration_summary": {
                "status": "validated",
                "brier_score": 0.08,
                "test_retest_reliability": 0.91,
                "dif_profiles_evaluated": 8,
                "temporal_drift_evaluated": True,
            },
            "evidence": {
                "protocol_hash": "sha256:" + "1" * 64,
                "calibration_dataset_hash": "sha256:" + "2" * 64,
                "locked_holdout_hash": "sha256:" + "3" * 64,
                "reference_adjudication_hash": "sha256:" + "4" * 64,
                "holdout_labels_accessed_after_preregistration": True,
            },
            "mandatory_criterion_floors": {
                criterion: 2 for criterion in _REQUIRED_CRITERIA
            },
            "minimum_criterion_scores": {
                criterion: 0.5 for criterion in _REQUIRED_CRITERIA
            },
        }
    )
    return payload


def _load(
    payload: dict[str, object],
    *,
    runtime_contracts: dict[str, str | None] | None = None,
):
    """Load one synthetic artifact through the production integrity boundary."""
    manifest = _manifest_for(_POLICY_NAME, payload)
    return load_policy_artifact(
        artifact_name=_POLICY_NAME,
        artifact_bytes=_canonical_bytes(payload),
        manifest_bytes=_canonical_bytes(manifest),
        now=_NOW,
        runtime_contracts=runtime_contracts or _RUNTIME_CONTRACTS,
    )


def test_policy_schema_declares_strict_lifecycle_and_publish_decision() -> None:
    """Keep lifecycle/publication fields explicit and closed to unknown values."""
    schema = json.loads(
        (_POLICY_DIR / "email_writing_judge_policy.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["additionalProperties"] is False
    assert schema["properties"]["publish_decision"]["enum"] == ["publish", "withhold"]
    assert schema["properties"]["status"]["enum"] == [
        "evaluation_only",
        "published",
        "superseded",
        "revoked",
    ]


@pytest.mark.parametrize("field", ["publish_decision", "status", "policy_version"])
def test_policy_rejects_missing_required_top_level_field(field: str) -> None:
    """A policy missing lifecycle identity cannot enter the runtime registry."""
    payload = _evaluation_policy()
    del payload[field]
    with pytest.raises(EmailWritingPolicyError, match="policy_schema_invalid"):
        _load(payload)


def test_evaluation_only_policy_must_withhold() -> None:
    """An evaluation artifact can exercise the pipeline but cannot publish guidance."""
    payload = _evaluation_policy()
    payload["publish_decision"] = "publish"
    with pytest.raises(EmailWritingPolicyError, match="policy_lifecycle_invalid"):
        _load(payload)


def test_policy_rejects_unknown_and_executable_fields() -> None:
    """Field smuggling cannot add lexical tables, scripts, or executable policy content."""
    for field, value in (
        ("keyword_table", {"urgent": "critical"}),
        ("executable", "python -c 'print(1)'"),
    ):
        payload = _evaluation_policy()
        payload[field] = value
        with pytest.raises(EmailWritingPolicyError, match="policy_schema_invalid"):
            _load(payload)


def test_manifest_rejects_malformed_and_modified_artifacts() -> None:
    """Only an exact artifact digest listed in the manifest can be loaded."""
    payload = _evaluation_policy()
    bad_manifest = {
        "manifest_version": 1,
        "artifacts": {_POLICY_NAME: {"sha256": "not-a-digest"}},
    }
    with pytest.raises(EmailWritingPolicyError, match="policy_manifest_invalid"):
        load_policy_artifact(
            artifact_name=_POLICY_NAME,
            artifact_bytes=_canonical_bytes(payload),
            manifest_bytes=_canonical_bytes(bad_manifest),
            now=_NOW,
            runtime_contracts=_RUNTIME_CONTRACTS,
        )

    manifest = _manifest_for(_POLICY_NAME, payload)
    payload["limitations"] = ["modified after manifest creation"]
    with pytest.raises(EmailWritingPolicyError, match="policy_integrity_mismatch"):
        load_policy_artifact(
            artifact_name=_POLICY_NAME,
            artifact_bytes=_canonical_bytes(payload),
            manifest_bytes=_canonical_bytes(manifest),
            now=_NOW,
            runtime_contracts=_RUNTIME_CONTRACTS,
        )


def test_evaluation_only_artifact_never_admits_user_facing_diagnostics() -> None:
    """Runtime admission remains withheld even when Judge evidence is otherwise strong."""
    policy = _load(_evaluation_policy())
    outcome = evaluate_policy_admission(
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
    )
    assert outcome == "withhold"


def test_published_policy_requires_complete_calibration_and_holdout_evidence() -> None:
    """Publication is invalid before preregistered holdout and adjudication evidence exists."""
    payload = _published_policy()
    payload["evidence"]["locked_holdout_hash"] = None
    with pytest.raises(EmailWritingPolicyError, match="policy_publication_evidence_incomplete"):
        _load(
            payload,
            runtime_contracts={
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.2",
                "contextual_orchestrator": "v1",
            },
        )


def test_profile_and_contract_mismatch_fail_closed() -> None:
    """Unsupported runtime contracts and language profiles cannot silently broaden claims."""
    payload = _published_policy()
    with pytest.raises(EmailWritingPolicyError, match="policy_contract_incompatible"):
        _load(
            payload,
            runtime_contracts={
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.1",
                "contextual_orchestrator": "v1",
            },
        )

    policy = _load(
        payload,
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    assert (
        evaluate_policy_admission(
            policy=policy,
            language_tag="fr",
            review_mode="deep",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="independent-judge-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            criterion_categories={criterion: 3 for criterion in _REQUIRED_CRITERIA},
            criterion_scores={criterion: 1.0 for criterion in _REQUIRED_CRITERIA},
        )
        == "unsupported_profile"
    )


def test_mandatory_preservation_floor_cannot_be_hidden_by_high_average() -> None:
    """A failed fact-preservation criterion withholds even when every other score is perfect."""
    payload = _published_policy()
    policy = _load(
        payload,
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    categories = {criterion: 3 for criterion in _REQUIRED_CRITERIA}
    scores = {criterion: 1.0 for criterion in _REQUIRED_CRITERIA}
    categories["fact_preservation"] = 1
    scores["fact_preservation"] = 0.99
    assert (
        evaluate_policy_admission(
            policy=policy,
            language_tag="en",
            review_mode="deep",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="independent-judge-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            criterion_categories=categories,
            criterion_scores=scores,
        )
        == "withhold"
    )


def test_same_model_candidate_and_judge_requires_published_compatibility() -> None:
    """A same-model pair is adjudicated unless the policy explicitly calibrates that pairing."""
    payload = _published_policy()
    profile = payload["approved_profiles"][0]
    profile["judge_model_profile_id"] = profile["candidate_model_profile_id"]
    profile["same_model_allowed"] = False
    policy = _load(
        payload,
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    assert (
        evaluate_policy_admission(
            policy=policy,
            language_tag="en",
            review_mode="deep",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="candidate-reviewer-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            criterion_categories={criterion: 3 for criterion in _REQUIRED_CRITERIA},
            criterion_scores={criterion: 1.0 for criterion in _REQUIRED_CRITERIA},
        )
        == "adjudicate"
    )


def test_mixed_criterion_identity_and_impossible_floors_fail_closed() -> None:
    """Criterion identity and category semantics stay fixed rather than being coerced."""
    payload = _published_policy()
    payload["mandatory_criterion_floors"]["fact_preservation"] = 4
    with pytest.raises(EmailWritingPolicyError, match="policy_floor_invalid"):
        _load(
            payload,
            runtime_contracts={
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.2",
                "contextual_orchestrator": "v1",
            },
        )

    payload = _published_policy()
    policy = _load(
        payload,
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    categories = {criterion: 3 for criterion in _REQUIRED_CRITERIA}
    categories["invented_criterion"] = 3
    with pytest.raises(EmailWritingPolicyError, match="criterion_identity_mismatch"):
        evaluate_policy_admission(
            policy=policy,
            language_tag="en",
            review_mode="deep",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="independent-judge-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            criterion_categories=categories,
            criterion_scores={criterion: 1.0 for criterion in _REQUIRED_CRITERIA},
        )


def test_revoked_policy_rolls_back_only_to_explicit_compatible_manifest_entry() -> None:
    """Rollback cannot silently downgrade to an unlisted, expired, or incompatible artifact."""
    current_payload = _published_policy(version="email-writing-policy-v2")
    current_payload["status"] = "revoked"
    current_payload["publish_decision"] = "withhold"
    current_payload["rollback_version"] = "email-writing-policy-v1"
    previous_payload = _published_policy(version="email-writing-policy-v1")

    current = _load(
        current_payload,
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    previous = _load(
        previous_payload,
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    assert select_rollback_policy(current_policy=current, candidates=[previous]) is previous

    unlisted = deepcopy(previous)
    object.__setattr__(unlisted, "policy_version", "email-writing-policy-v0")
    with pytest.raises(EmailWritingPolicyError, match="policy_rollback_unavailable"):
        select_rollback_policy(current_policy=current, candidates=[unlisted])
