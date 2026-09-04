"""Regression contract for versioned email-writing Judge admission policy."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from services.email_writing_policy import (
    EmailWritingCalibrationSummary,
    EmailWritingJudgePolicy,
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


def _published_evidence_artifacts(payload: dict[str, object]) -> dict[str, bytes]:
    """Build immutable evidence envelopes and bind their digests to the policy."""
    evidence = payload["evidence"]
    assert isinstance(evidence, dict)
    artifacts: dict[str, bytes] = {}
    protocol_bytes = _canonical_bytes(
        {
            "evidence_version": 1,
            "evidence_kind": "protocol",
            "recorded_at": "2026-08-01T00:00:00Z",
            "protocol_hash": None,
        }
    )
    protocol_hash = "sha256:" + hashlib.sha256(protocol_bytes).hexdigest()
    if evidence.get("protocol_hash") == "sha256:" + "1" * 64:
        evidence["protocol_hash"] = protocol_hash
    artifacts[protocol_hash] = protocol_bytes
    for index, evidence_kind in enumerate(
        ("calibration_dataset", "locked_holdout", "reference_adjudication"),
        start=2,
    ):
        artifact_bytes = _canonical_bytes(
            {
                "evidence_version": 1,
                "evidence_kind": evidence_kind,
                "recorded_at": f"2026-08-0{index}T00:00:00Z",
                "protocol_hash": protocol_hash,
            }
        )
        qualified_digest = "sha256:" + hashlib.sha256(artifact_bytes).hexdigest()
        field_name = f"{evidence_kind}_hash"
        placeholder_digit = str(index)
        if evidence.get(field_name) == "sha256:" + placeholder_digit * 64:
            evidence[field_name] = qualified_digest
        artifacts[qualified_digest] = artifact_bytes
    return artifacts


def _load(
    payload: dict[str, object],
    *,
    runtime_contracts: dict[str, str | None] | None = None,
):
    """Load one synthetic artifact through the production integrity boundary."""
    evidence_artifacts = (
        _published_evidence_artifacts(payload)
        if payload.get("status") == "published"
        else None
    )
    manifest = _manifest_for(_POLICY_NAME, payload)
    return load_policy_artifact(
        artifact_name=_POLICY_NAME,
        artifact_bytes=_canonical_bytes(payload),
        manifest_bytes=_canonical_bytes(manifest),
        now=_NOW,
        runtime_contracts=runtime_contracts or _RUNTIME_CONTRACTS,
        evidence_artifacts=evidence_artifacts,
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
    published_contract = schema["allOf"][0]["then"]["properties"]
    assert published_contract["calibration_summary"]["properties"]["status"] == {
        "const": "validated"
    }
    assert published_contract["evidence"]["properties"]["protocol_hash"] == {
        "type": "string"
    }
    assert published_contract["evidence"]["properties"][
        "holdout_labels_accessed_after_preregistration"
    ] == {"const": True}


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
    with pytest.raises(
        EmailWritingPolicyError, match="policy_publication_evidence_incomplete"
    ):
        _load(
            payload,
            runtime_contracts={
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.2",
                "contextual_orchestrator": "v1",
            },
        )


def test_published_policy_resolves_evidence_bytes_and_preregistration_order() -> None:
    """Reject missing, modified, or pre-protocol published evidence artifacts."""
    payload = _published_policy()
    evidence_artifacts = _published_evidence_artifacts(payload)
    manifest = _manifest_for(_POLICY_NAME, payload)
    common = {
        "artifact_name": _POLICY_NAME,
        "artifact_bytes": _canonical_bytes(payload),
        "manifest_bytes": _canonical_bytes(manifest),
        "now": _NOW,
        "runtime_contracts": {
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    }
    with pytest.raises(
        EmailWritingPolicyError, match="policy_publication_evidence_unverified"
    ):
        load_policy_artifact(**common)

    modified = dict(evidence_artifacts)
    modified[next(iter(modified))] += b"modified"
    with pytest.raises(
        EmailWritingPolicyError, match="policy_publication_evidence_mismatch"
    ):
        load_policy_artifact(**common, evidence_artifacts=modified)

    evidence = payload["evidence"]
    assert isinstance(evidence, dict)
    old_holdout_hash = evidence["locked_holdout_hash"]
    assert isinstance(old_holdout_hash, str)
    early_holdout = _canonical_bytes(
        {
            "evidence_version": 1,
            "evidence_kind": "locked_holdout",
            "recorded_at": "2026-07-31T00:00:00Z",
            "protocol_hash": evidence["protocol_hash"],
        }
    )
    new_holdout_hash = "sha256:" + hashlib.sha256(early_holdout).hexdigest()
    evidence["locked_holdout_hash"] = new_holdout_hash
    evidence_artifacts.pop(old_holdout_hash)
    evidence_artifacts[new_holdout_hash] = early_holdout
    common["artifact_bytes"] = _canonical_bytes(payload)
    common["manifest_bytes"] = _canonical_bytes(_manifest_for(_POLICY_NAME, payload))
    with pytest.raises(
        EmailWritingPolicyError, match="policy_publication_evidence_order_invalid"
    ):
        load_policy_artifact(**common, evidence_artifacts=evidence_artifacts)


def test_published_evidence_envelopes_fail_closed_on_identity_mismatch() -> None:
    """Reject missing, malformed, mislabeled, and self-referential evidence."""

    def load_with(
        payload: dict[str, object], artifacts: dict[str, bytes]
    ) -> EmailWritingJudgePolicy:
        return load_policy_artifact(
            artifact_name=_POLICY_NAME,
            artifact_bytes=_canonical_bytes(payload),
            manifest_bytes=_canonical_bytes(_manifest_for(_POLICY_NAME, payload)),
            now=_NOW,
            runtime_contracts={
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.2",
                "contextual_orchestrator": "v1",
            },
            evidence_artifacts=artifacts,
        )

    payload = _published_policy()
    artifacts = _published_evidence_artifacts(payload)
    missing = dict(artifacts)
    missing.pop(next(iter(missing)))
    with pytest.raises(
        EmailWritingPolicyError, match="policy_publication_evidence_unverified"
    ):
        load_with(payload, missing)

    for evidence_kind, replacement, expected_code in (
        (
            "calibration_dataset",
            {
                "evidence_version": 1,
                "evidence_kind": "calibration_dataset",
                "recorded_at": "2026-08-02T00:00:00Z",
                "protocol_hash": "invalid",
            },
            "policy_publication_evidence_invalid",
        ),
        (
            "locked_holdout",
            {
                "evidence_version": 1,
                "evidence_kind": "reference_adjudication",
                "recorded_at": "2026-08-03T00:00:00Z",
                "protocol_hash": payload["evidence"]["protocol_hash"],
            },
            "policy_publication_evidence_invalid",
        ),
        (
            "protocol",
            {
                "evidence_version": 1,
                "evidence_kind": "protocol",
                "recorded_at": "2026-08-01T00:00:00Z",
                "protocol_hash": "sha256:" + "0" * 64,
            },
            "policy_publication_evidence_invalid",
        ),
    ):
        current_payload = deepcopy(payload)
        current_artifacts = dict(artifacts)
        evidence = current_payload["evidence"]
        assert isinstance(evidence, dict)
        field_name = f"{evidence_kind}_hash"
        old_hash = evidence[field_name]
        assert isinstance(old_hash, str)
        replacement_bytes = _canonical_bytes(replacement)
        replacement_hash = "sha256:" + hashlib.sha256(replacement_bytes).hexdigest()
        evidence[field_name] = replacement_hash
        current_artifacts.pop(old_hash)
        current_artifacts[replacement_hash] = replacement_bytes

        with pytest.raises(EmailWritingPolicyError, match=expected_code):
            load_with(current_payload, current_artifacts)


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
    """Rollback cannot silently downgrade to an unlisted artifact."""
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
    assert (
        select_rollback_policy(current_policy=current, candidates=[previous])
        is previous
    )

    unlisted = deepcopy(previous)
    object.__setattr__(unlisted, "policy_version", "email-writing-policy-v0")
    with pytest.raises(EmailWritingPolicyError, match="policy_rollback_unavailable"):
        select_rollback_policy(current_policy=current, candidates=[unlisted])


def _assert_policy_rejected(payload: dict[str, object], code: str) -> None:
    """Require one mutated policy to fail with a stable public error code."""
    with pytest.raises(EmailWritingPolicyError, match=code):
        _load(
            payload,
            runtime_contracts={
                "naruon": "0.14.4",
                "inkspan": "0.6.0",
                "fast_mlsirm": "0.9.2",
                "contextual_orchestrator": "v1",
            },
        )


def test_policy_error_repr_and_manifest_boundaries() -> None:
    """Cover redacted error display and manifest allowlist edge cases."""
    assert repr(EmailWritingPolicyError("policy_invalid")) == (
        "EmailWritingPolicyError('policy_invalid')"
    )
    payload = _evaluation_policy()
    for artifacts in ({}, {"../policy.json": {"sha256": "0" * 64}}):
        manifest = {"manifest_version": 1, "artifacts": artifacts}
        with pytest.raises(EmailWritingPolicyError, match="policy_manifest_invalid"):
            load_policy_artifact(
                artifact_name=_POLICY_NAME,
                artifact_bytes=_canonical_bytes(payload),
                manifest_bytes=_canonical_bytes(manifest),
                now=_NOW,
                runtime_contracts=_RUNTIME_CONTRACTS,
            )

    with pytest.raises(
        EmailWritingPolicyError, match="policy_manifest_unknown_artifact"
    ):
        load_policy_artifact(
            artifact_name="unknown.json",
            artifact_bytes=_canonical_bytes(payload),
            manifest_bytes=_canonical_bytes(_manifest_for(_POLICY_NAME, payload)),
            now=_NOW,
            runtime_contracts=_RUNTIME_CONTRACTS,
        )


def test_policy_field_validators_reject_invalid_values() -> None:
    """Exercise every bounded identity, profile, metric, and list validator."""
    mutations = []

    payload = _evaluation_policy()
    payload["compatible_contracts"]["naruon"] = "bad path/value"
    mutations.append(payload)

    for field in (
        "profile_id",
        "candidate_model_profile_id",
        "candidate_provider_id",
        "judge_model_profile_id",
        "judge_provider_id",
        "rubric_version",
    ):
        payload = _evaluation_policy()
        payload["approved_profiles"][0][field] = "bad path/value"
        mutations.append(payload)

    for language_tags in ([], ["en", "en"], ["*"]):
        payload = _evaluation_policy()
        payload["approved_profiles"][0]["language_tags"] = language_tags
        mutations.append(payload)

    for review_modes in ([], ["deep", "deep"]):
        payload = _evaluation_policy()
        payload["approved_profiles"][0]["review_modes"] = review_modes
        mutations.append(payload)

    for field, value in (
        ("brier_score", float("nan")),
        ("brier_score", 1.1),
        ("test_retest_reliability", float("inf")),
        ("dif_profiles_evaluated", -1),
    ):
        payload = _evaluation_policy()
        payload["calibration_summary"][field] = value
        mutations.append(payload)

    payload = _evaluation_policy()
    payload["evidence"]["protocol_hash"] = "not-a-qualified-hash"
    mutations.append(payload)

    payload = _evaluation_policy()
    payload["policy_id"] = "bad path/value"
    mutations.append(payload)

    for payload in mutations:
        _assert_policy_rejected(payload, "policy_schema_invalid")


def test_policy_collection_validators_reject_invalid_values() -> None:
    """Reject empty, duplicate, unknown, unordered, and inconsistent policy maps."""
    mutations = []
    for profiles in ([], [_evaluation_policy()["approved_profiles"][0]] * 2):
        payload = _evaluation_policy()
        payload["approved_profiles"] = deepcopy(profiles)
        mutations.append(payload)

    for category_count in (1, 10):
        payload = _evaluation_policy()
        payload["category_count"] = category_count
        mutations.append(payload)

    for anchors in ([], ["same", "same"], ["bad anchor", "b", "c", "d"]):
        payload = _evaluation_policy()
        payload["category_anchors"] = anchors
        mutations.append(payload)

    for conditions in (
        ["criterion_disagreement", "criterion_disagreement"],
        ["unknown_condition"],
    ):
        payload = _evaluation_policy()
        payload["adjudication_conditions"] = conditions
        mutations.append(payload)

    for limitations in ([], [""]):
        payload = _evaluation_policy()
        payload["limitations"] = limitations
        mutations.append(payload)

    payload = _evaluation_policy()
    payload["category_anchors"] = payload["category_anchors"][:-1]
    mutations.append(payload)

    payload = _evaluation_policy()
    payload["required_criteria_by_candidate_kind"] = {
        "replacement_diagnostic": list(_REQUIRED_CRITERIA)
    }
    mutations.append(payload)

    for criterion_ids in (
        [],
        ["invented_criterion"],
        list(reversed(_REQUIRED_CRITERIA)),
        [
            criterion
            for criterion in _REQUIRED_CRITERIA
            if criterion != "replacement_correctness"
        ],
    ):
        payload = _evaluation_policy()
        payload["required_criteria_by_candidate_kind"]["replacement_diagnostic"] = (
            criterion_ids
        )
        mutations.append(payload)

    payload = _evaluation_policy()
    payload["required_criteria_by_candidate_kind"]["no_replacement_diagnostic"].insert(
        2, "replacement_correctness"
    )
    mutations.append(payload)

    payload = _evaluation_policy()
    payload["mandatory_criterion_floors"].pop("fact_preservation")
    mutations.append(payload)

    payload = _evaluation_policy()
    payload["minimum_criterion_scores"].pop("fact_preservation")
    mutations.append(payload)

    for score in (float("nan"), 1.1):
        payload = _evaluation_policy()
        payload["minimum_criterion_scores"]["fact_preservation"] = score
        mutations.append(payload)

    for payload in mutations:
        _assert_policy_rejected(payload, "policy_schema_invalid")

    with pytest.raises(ValueError, match="calibration_metric_non_finite"):
        EmailWritingCalibrationSummary(
            status="validated",
            brier_score=float("nan"),
            test_retest_reliability=0.9,
            dif_profiles_evaluated=1,
            temporal_drift_evaluated=True,
        )

    payload = _evaluation_policy()
    payload["minimum_criterion_scores"]["fact_preservation"] = float("nan")
    with pytest.raises(ValueError, match="policy_score_floor_non_finite"):
        EmailWritingJudgePolicy.model_validate(payload)


def test_policy_lifecycle_evidence_requirements() -> None:
    """Reject every incomplete publication and evaluation-only holdout state."""
    lifecycle_cases = []

    payload = _published_policy()
    payload["publish_decision"] = "withhold"
    lifecycle_cases.append((payload, "policy_lifecycle_invalid"))

    payload = _evaluation_policy()
    payload["evidence"]["holdout_labels_accessed_after_preregistration"] = True
    lifecycle_cases.append((payload, "policy_lifecycle_invalid"))

    payload = _published_policy()
    payload["calibration_summary"]["status"] = "not_evaluated"
    lifecycle_cases.append((payload, "policy_publication_evidence_incomplete"))

    for section, field, value in (
        ("evidence", "holdout_labels_accessed_after_preregistration", False),
        ("calibration_summary", "brier_score", None),
        ("calibration_summary", "test_retest_reliability", None),
        ("calibration_summary", "dif_profiles_evaluated", 0),
        ("calibration_summary", "temporal_drift_evaluated", False),
    ):
        payload = _published_policy()
        payload[section][field] = value
        lifecycle_cases.append((payload, "policy_publication_evidence_incomplete"))

    for payload, code in lifecycle_cases:
        _assert_policy_rejected(payload, code)


def test_policy_time_and_runtime_contract_boundaries() -> None:
    """Reject malformed clocks, invalid windows, and incomplete runtime maps."""
    payload = _evaluation_policy()
    payload["created_at"] = "not-a-time"
    _assert_policy_rejected(payload, "policy_schema_invalid")

    payload = _evaluation_policy()
    payload["created_at"] = "2026-09-01T00:00:00"
    _assert_policy_rejected(payload, "policy_schema_invalid")

    payload = _evaluation_policy()
    manifest = _manifest_for(_POLICY_NAME, payload)
    common = {
        "artifact_name": _POLICY_NAME,
        "artifact_bytes": _canonical_bytes(payload),
        "manifest_bytes": _canonical_bytes(manifest),
        "runtime_contracts": _RUNTIME_CONTRACTS,
    }
    for now, code in (
        (datetime(2026, 9, 2), "policy_clock_invalid"),
        (datetime(2025, 9, 2, tzinfo=timezone.utc), "policy_future_dated"),
        (datetime(2028, 9, 2, tzinfo=timezone.utc), "policy_expired"),
    ):
        with pytest.raises(EmailWritingPolicyError, match=code):
            load_policy_artifact(now=now, **common)

    payload["expires_at"] = payload["created_at"]
    with pytest.raises(EmailWritingPolicyError, match="policy_time_window_invalid"):
        load_policy_artifact(
            artifact_name=_POLICY_NAME,
            artifact_bytes=_canonical_bytes(payload),
            manifest_bytes=_canonical_bytes(_manifest_for(_POLICY_NAME, payload)),
            now=_NOW,
            runtime_contracts=_RUNTIME_CONTRACTS,
        )

    with pytest.raises(EmailWritingPolicyError, match="policy_contract_incompatible"):
        _load(_evaluation_policy(), runtime_contracts={"naruon": "0.14.4"})


def test_published_policy_admission_value_boundaries() -> None:
    """Cover category, score, threshold, and successful admission outcomes."""
    policy = _load(
        _published_policy(),
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    categories = {criterion: 3 for criterion in _REQUIRED_CRITERIA}
    scores = {criterion: 1.0 for criterion in _REQUIRED_CRITERIA}

    def evaluate(current_categories: dict[str, int], current_scores: dict[str, float]):
        return evaluate_policy_admission(
            policy=policy,
            language_tag="en",
            review_mode="deep",
            candidate_model_profile_id="candidate-reviewer-v1",
            candidate_provider_id="contextual-orchestrator",
            judge_model_profile_id="independent-judge-v1",
            judge_provider_id="contextual-orchestrator",
            rubric_version="email_writing_judge_rubric_v1",
            criterion_categories=current_categories,
            criterion_scores=current_scores,
        )

    assert evaluate(categories, scores) == "admit"

    for value in (True, -1, policy.category_count):
        invalid_categories = dict(categories)
        invalid_categories["fact_preservation"] = value
        with pytest.raises(EmailWritingPolicyError, match="criterion_category_invalid"):
            evaluate(invalid_categories, scores)

    for value in (True, float("nan"), float("inf"), -0.1, 1.1):
        invalid_scores = dict(scores)
        invalid_scores["fact_preservation"] = value
        with pytest.raises(EmailWritingPolicyError, match="criterion_score_invalid"):
            evaluate(categories, invalid_scores)

    below_floor = dict(scores)
    below_floor["fact_preservation"] = 0.1
    assert evaluate(categories, below_floor) == "withhold"


def test_rollback_requires_an_explicit_version() -> None:
    """A policy without a named rollback target cannot select a candidate."""
    current = _load(
        _published_policy(),
        runtime_contracts={
            "naruon": "0.14.4",
            "inkspan": "0.6.0",
            "fast_mlsirm": "0.9.2",
            "contextual_orchestrator": "v1",
        },
    )
    with pytest.raises(EmailWritingPolicyError, match="policy_rollback_unavailable"):
        select_rollback_policy(current_policy=current, candidates=[])
