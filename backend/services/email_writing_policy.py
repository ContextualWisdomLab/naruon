"""Integrity-bound admission policy for contextual email-writing diagnostics.

This module validates versioned policy artifacts and decides whether already
structured Judge evidence may be admitted, withheld, or escalated. It does not
infer writing quality from text, fit calibration models, call model providers,
mutate mail, or decide whether an email may be sent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import re
from typing import Final, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from services.email_writing_contracts import (
    StrictEmailWritingJsonError,
    parse_strict_email_writing_json,
)
from services.email_writing_judge import EMAIL_WRITING_JUDGE_CRITERION_IDS

PolicyStatus: TypeAlias = Literal[
    "evaluation_only",
    "published",
    "superseded",
    "revoked",
]
PublishDecision: TypeAlias = Literal["publish", "withhold"]
AdmissionOutcome: TypeAlias = Literal[
    "admit",
    "withhold",
    "adjudicate",
    "unsupported_profile",
    "policy_unavailable",
]
CandidateKind: TypeAlias = Literal[
    "replacement_diagnostic",
    "no_replacement_diagnostic",
]
ReviewMode: TypeAlias = Literal["incremental", "deep"]

_HASH_RE: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX_DIGEST_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ALLOWED_ADJUDICATION_CONDITIONS: Final = frozenset(
    {
        "same_model_without_compatible_calibration",
        "criterion_disagreement",
        "insufficient_evidence",
    }
)
_CANDIDATE_KINDS: Final = (
    "replacement_diagnostic",
    "no_replacement_diagnostic",
)


class EmailWritingPolicyError(ValueError):
    """Stable payload-redacted failure raised by policy integrity validation."""

    def __init__(self, code: str) -> None:
        """Create an error that exposes only one stable application code."""
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        """Return a representation that cannot contain policy payload text."""
        return f"EmailWritingPolicyError({self.code!r})"


class _PolicyModel(BaseModel):
    """Strict base class for immutable policy and manifest JSON models."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _ManifestArtifact(_PolicyModel):
    """Digest identity for one policy artifact listed by the manifest."""

    sha256: StrictStr

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """Require one lowercase SHA-256 digest without an algorithm prefix."""
        if _HEX_DIGEST_RE.fullmatch(value) is None:
            raise ValueError("manifest_digest_invalid")
        return value


class _PolicyManifest(_PolicyModel):
    """Exact artifact allowlist used before any policy JSON is trusted."""

    manifest_version: Literal[1]
    artifacts: dict[str, _ManifestArtifact]

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts(
        cls,
        value: dict[str, _ManifestArtifact],
    ) -> dict[str, _ManifestArtifact]:
        """Require at least one safely named immutable JSON artifact."""
        if not value:
            raise ValueError("manifest_artifacts_empty")
        for name in value:
            if (
                not name.endswith(".json")
                or "/" in name
                or "\\" in name
                or name.startswith(".")
                or ".." in name
            ):
                raise ValueError("manifest_artifact_name_invalid")
        return value


class EmailWritingCompatibleContracts(_PolicyModel):
    """Exact runtime contract versions against which a policy was evaluated."""

    naruon: StrictStr
    inkspan: StrictStr | None
    fast_mlsirm: StrictStr | None
    contextual_orchestrator: StrictStr

    @field_validator("naruon", "inkspan", "fast_mlsirm", "contextual_orchestrator")
    @classmethod
    def validate_contract_id(cls, value: str | None) -> str | None:
        """Keep non-null dependency identities bounded and non-executable."""
        if value is None:
            return None
        if _IDENTIFIER_RE.fullmatch(value) is None:
            raise ValueError("contract_identity_invalid")
        return value


class EmailWritingApprovedProfile(_PolicyModel):
    """One explicitly evaluated language/model/provider/rubric combination."""

    profile_id: StrictStr
    language_tags: list[StrictStr]
    review_modes: list[ReviewMode]
    candidate_model_profile_id: StrictStr
    candidate_provider_id: StrictStr
    judge_model_profile_id: StrictStr
    judge_provider_id: StrictStr
    rubric_version: StrictStr
    same_model_allowed: StrictBool

    @field_validator(
        "profile_id",
        "candidate_model_profile_id",
        "candidate_provider_id",
        "judge_model_profile_id",
        "judge_provider_id",
        "rubric_version",
    )
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        """Reject profile identifiers that could smuggle commands or paths."""
        if _IDENTIFIER_RE.fullmatch(value) is None:
            raise ValueError("profile_identity_invalid")
        return value

    @field_validator("language_tags")
    @classmethod
    def validate_language_tags(cls, value: list[str]) -> list[str]:
        """Require an explicit non-empty language claim without wildcard profiles."""
        if not value or len(set(value)) != len(value):
            raise ValueError("language_profiles_invalid")
        for language_tag in value:
            if (
                not language_tag
                or language_tag == "*"
                or len(language_tag) > 63
                or any(character.isspace() for character in language_tag)
            ):
                raise ValueError("language_profile_invalid")
        return value

    @field_validator("review_modes")
    @classmethod
    def validate_review_modes(cls, value: list[ReviewMode]) -> list[ReviewMode]:
        """Require at least one unique supported review mode."""
        if not value or len(set(value)) != len(value):
            raise ValueError("review_modes_invalid")
        return value


class EmailWritingCalibrationSummary(_PolicyModel):
    """Privacy-minimized measurement summary required before publication."""

    status: Literal["not_evaluated", "validated"]
    brier_score: StrictFloat | None
    test_retest_reliability: StrictFloat | None
    dif_profiles_evaluated: StrictInt
    temporal_drift_evaluated: StrictBool

    @field_validator("brier_score", "test_retest_reliability")
    @classmethod
    def validate_unit_metric(cls, value: float | None) -> float | None:
        """Require finite unit-interval metrics when measurement evidence exists."""
        if value is None:
            return None
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("calibration_metric_non_finite")
        if not 0.0 <= value <= 1.0:
            raise ValueError("calibration_metric_out_of_range")
        return value

    @field_validator("dif_profiles_evaluated")
    @classmethod
    def validate_dif_count(cls, value: int) -> int:
        """Require a non-negative count of explicitly evaluated DIF profiles."""
        if value < 0:
            raise ValueError("dif_profile_count_invalid")
        return value


class EmailWritingPolicyEvidence(_PolicyModel):
    """Content hashes proving preregistration and evaluated reference material."""

    protocol_hash: StrictStr | None
    calibration_dataset_hash: StrictStr | None
    locked_holdout_hash: StrictStr | None
    reference_adjudication_hash: StrictStr | None
    holdout_labels_accessed_after_preregistration: StrictBool

    @field_validator(
        "protocol_hash",
        "calibration_dataset_hash",
        "locked_holdout_hash",
        "reference_adjudication_hash",
    )
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        """Require algorithm-qualified SHA-256 identities when evidence exists."""
        if value is not None and _HASH_RE.fullmatch(value) is None:
            raise ValueError("evidence_hash_invalid")
        return value


class EmailWritingJudgePolicy(_PolicyModel):
    """Validated policy artifact that contains no authored or model plaintext."""

    policy_id: StrictStr
    policy_version: StrictStr
    status: PolicyStatus
    publish_decision: PublishDecision
    created_at: StrictStr
    expires_at: StrictStr
    compatible_contracts: EmailWritingCompatibleContracts
    approved_profiles: list[EmailWritingApprovedProfile]
    category_count: StrictInt
    category_anchors: list[StrictStr]
    required_criteria_by_candidate_kind: dict[str, list[StrictStr]]
    mandatory_criterion_floors: dict[str, StrictInt]
    minimum_criterion_scores: dict[str, StrictFloat]
    adjudication_conditions: list[StrictStr]
    calibration_summary: EmailWritingCalibrationSummary
    evidence: EmailWritingPolicyEvidence
    limitations: list[StrictStr]
    rollback_version: StrictStr | None

    _artifact_name: str = PrivateAttr(default="")
    _artifact_sha256: str = PrivateAttr(default="")

    @field_validator("policy_id", "policy_version", "rollback_version")
    @classmethod
    def validate_policy_identifier(cls, value: str | None) -> str | None:
        """Require bounded opaque policy identities rather than executable text."""
        if value is None:
            return None
        if _IDENTIFIER_RE.fullmatch(value) is None:
            raise ValueError("policy_identity_invalid")
        return value

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        """Require an offset-aware RFC 3339-compatible timestamp."""
        _parse_timestamp(value)
        return value

    @field_validator("approved_profiles")
    @classmethod
    def validate_profiles(
        cls,
        value: list[EmailWritingApprovedProfile],
    ) -> list[EmailWritingApprovedProfile]:
        """Require unique profile identities and at least one bounded profile."""
        if not value:
            raise ValueError("approved_profiles_empty")
        profile_ids = [profile.profile_id for profile in value]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("approved_profile_duplicate")
        return value

    @field_validator("category_count")
    @classmethod
    def validate_category_count(cls, value: int) -> int:
        """Bound ordered polytomous categories without selecting a production value."""
        if value < 2 or value > 9:
            raise ValueError("category_count_invalid")
        return value

    @field_validator("category_anchors")
    @classmethod
    def validate_anchors(cls, value: list[str]) -> list[str]:
        """Require unique stable anchor identities without interpreting prose."""
        if not value or len(value) != len(set(value)):
            raise ValueError("category_anchors_invalid")
        for anchor in value:
            if _IDENTIFIER_RE.fullmatch(anchor) is None:
                raise ValueError("category_anchor_invalid")
        return value

    @field_validator("adjudication_conditions")
    @classmethod
    def validate_adjudication_conditions(cls, value: list[str]) -> list[str]:
        """Restrict escalation triggers to structured workflow states."""
        if len(value) != len(set(value)):
            raise ValueError("adjudication_condition_duplicate")
        if not set(value).issubset(_ALLOWED_ADJUDICATION_CONDITIONS):
            raise ValueError("adjudication_condition_invalid")
        return value

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: list[str]) -> list[str]:
        """Keep limitations explicit, bounded, and non-empty for auditability."""
        if not value:
            raise ValueError("limitations_empty")
        for limitation in value:
            if not limitation or len(limitation) > 1_000:
                raise ValueError("limitation_invalid")
        return value

    @model_validator(mode="after")
    def validate_policy_contract(self) -> "EmailWritingJudgePolicy":
        """Enforce lifecycle, criterion, threshold, and evidence invariants."""
        if len(self.category_anchors) != self.category_count:
            raise ValueError("category_anchor_count_mismatch")

        required_keys = set(_CANDIDATE_KINDS)
        if set(self.required_criteria_by_candidate_kind) != required_keys:
            raise ValueError("candidate_kind_contract_invalid")
        canonical = tuple(EMAIL_WRITING_JUDGE_CRITERION_IDS)
        canonical_set = set(canonical)
        for candidate_kind, criterion_ids in self.required_criteria_by_candidate_kind.items():
            if not criterion_ids or len(criterion_ids) != len(set(criterion_ids)):
                raise ValueError("required_criteria_invalid")
            if not set(criterion_ids).issubset(canonical_set):
                raise ValueError("required_criteria_invalid")
            if tuple(criterion for criterion in canonical if criterion in criterion_ids) != tuple(
                criterion_ids
            ):
                raise ValueError("required_criteria_order_invalid")
            if candidate_kind == "replacement_diagnostic":
                if "replacement_correctness" not in criterion_ids:
                    raise ValueError("replacement_criterion_required")
            elif "replacement_correctness" in criterion_ids:
                raise ValueError("replacement_criterion_forbidden")

        expected_floor_ids = set().union(
            *(set(values) for values in self.required_criteria_by_candidate_kind.values())
        )
        if set(self.mandatory_criterion_floors) != expected_floor_ids:
            raise ValueError("criterion_floor_identity_invalid")
        if set(self.minimum_criterion_scores) != expected_floor_ids:
            raise ValueError("criterion_score_floor_identity_invalid")
        for floor in self.mandatory_criterion_floors.values():
            if floor < 0 or floor >= self.category_count:
                raise ValueError("policy_floor_invalid")
        for score in self.minimum_criterion_scores.values():
            if score != score or score in {float("inf"), float("-inf")}:
                raise ValueError("policy_score_floor_non_finite")
            if not 0.0 <= score <= 1.0:
                raise ValueError("policy_score_floor_invalid")

        if self.status == "published":
            if self.publish_decision != "publish":
                raise ValueError("published_policy_must_publish")
            if self.calibration_summary.status != "validated":
                raise ValueError("published_calibration_missing")
            if any(
                value is None
                for value in (
                    self.compatible_contracts.inkspan,
                    self.compatible_contracts.fast_mlsirm,
                    self.evidence.protocol_hash,
                    self.evidence.calibration_dataset_hash,
                    self.evidence.locked_holdout_hash,
                    self.evidence.reference_adjudication_hash,
                )
            ):
                raise ValueError("published_evidence_missing")
            if not self.evidence.holdout_labels_accessed_after_preregistration:
                raise ValueError("published_holdout_order_invalid")
            if self.calibration_summary.brier_score is None:
                raise ValueError("published_brier_missing")
            if self.calibration_summary.test_retest_reliability is None:
                raise ValueError("published_reliability_missing")
            if self.calibration_summary.dif_profiles_evaluated <= 0:
                raise ValueError("published_dif_missing")
            if not self.calibration_summary.temporal_drift_evaluated:
                raise ValueError("published_drift_missing")
        else:
            if self.publish_decision != "withhold":
                raise ValueError("nonpublished_policy_must_withhold")
            if self.status == "evaluation_only":
                if self.evidence.holdout_labels_accessed_after_preregistration:
                    raise ValueError("evaluation_holdout_access_forbidden")

        return self


def _parse_timestamp(value: str) -> datetime:
    """Parse one offset-aware policy timestamp and normalize it to UTC."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("policy_timestamp_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("policy_timestamp_timezone_required")
    return parsed.astimezone(timezone.utc)


def _wrap_policy_validation_error(
    error: Exception,
    *,
    default_code: str,
) -> EmailWritingPolicyError:
    """Map internal parser details to one stable redacted policy error code."""
    text = str(error)
    if "policy_floor_invalid" in text:
        return EmailWritingPolicyError("policy_floor_invalid")
    if any(
        marker in text
        for marker in (
            "nonpublished_policy_must_withhold",
            "published_policy_must_publish",
            "evaluation_holdout_access_forbidden",
        )
    ):
        return EmailWritingPolicyError("policy_lifecycle_invalid")
    if any(
        marker in text
        for marker in (
            "published_evidence_missing",
            "published_calibration_missing",
            "published_holdout_order_invalid",
            "published_brier_missing",
            "published_reliability_missing",
            "published_dif_missing",
            "published_drift_missing",
        )
    ):
        return EmailWritingPolicyError("policy_publication_evidence_incomplete")
    return EmailWritingPolicyError(default_code)


def _validate_runtime_contracts(
    policy: EmailWritingJudgePolicy,
    runtime_contracts: Mapping[str, str | None],
) -> None:
    """Require every non-null policy contract to match the live runtime exactly."""
    expected = {
        "naruon": policy.compatible_contracts.naruon,
        "inkspan": policy.compatible_contracts.inkspan,
        "fast_mlsirm": policy.compatible_contracts.fast_mlsirm,
        "contextual_orchestrator": policy.compatible_contracts.contextual_orchestrator,
    }
    if set(runtime_contracts) != set(expected):
        raise EmailWritingPolicyError("policy_contract_incompatible")
    for name, expected_version in expected.items():
        if expected_version is None:
            continue
        if runtime_contracts[name] != expected_version:
            raise EmailWritingPolicyError("policy_contract_incompatible")


def load_policy_artifact(
    *,
    artifact_name: str,
    artifact_bytes: bytes,
    manifest_bytes: bytes,
    now: datetime,
    runtime_contracts: Mapping[str, str | None],
) -> EmailWritingJudgePolicy:
    """Load one integrity-bound policy after strict manifest and lifecycle validation.

    The function validates bytes before parsing policy content, rejects duplicate
    or unexpected JSON members, checks temporal validity and exact runtime
    contracts, and returns no user-facing admission merely because an artifact
    loaded successfully.
    """
    try:
        manifest = parse_strict_email_writing_json(manifest_bytes, _PolicyManifest)
    except (StrictEmailWritingJsonError, ValidationError, ValueError) as error:
        raise EmailWritingPolicyError("policy_manifest_invalid") from error

    entry = manifest.artifacts.get(artifact_name)
    if entry is None:
        raise EmailWritingPolicyError("policy_manifest_unknown_artifact")
    actual_digest = hashlib.sha256(artifact_bytes).hexdigest()
    if actual_digest != entry.sha256:
        raise EmailWritingPolicyError("policy_integrity_mismatch")

    try:
        policy = parse_strict_email_writing_json(artifact_bytes, EmailWritingJudgePolicy)
    except (StrictEmailWritingJsonError, ValidationError, ValueError) as error:
        raise _wrap_policy_validation_error(
            error,
            default_code="policy_schema_invalid",
        ) from error

    if now.tzinfo is None:
        raise EmailWritingPolicyError("policy_clock_invalid")
    now_utc = now.astimezone(timezone.utc)
    created_at = _parse_timestamp(policy.created_at)
    expires_at = _parse_timestamp(policy.expires_at)
    if expires_at <= created_at:
        raise EmailWritingPolicyError("policy_time_window_invalid")
    if now_utc < created_at:
        raise EmailWritingPolicyError("policy_future_dated")
    if now_utc >= expires_at:
        raise EmailWritingPolicyError("policy_expired")

    _validate_runtime_contracts(policy, runtime_contracts)
    object.__setattr__(policy, "_artifact_name", artifact_name)
    object.__setattr__(policy, "_artifact_sha256", actual_digest)
    return policy


def evaluate_policy_admission(
    *,
    policy: EmailWritingJudgePolicy,
    language_tag: str,
    review_mode: ReviewMode,
    candidate_model_profile_id: str,
    candidate_provider_id: str,
    judge_model_profile_id: str,
    judge_provider_id: str,
    rubric_version: str,
    criterion_categories: Mapping[str, int],
    criterion_scores: Mapping[str, float],
    candidate_kind: CandidateKind = "replacement_diagnostic",
) -> AdmissionOutcome:
    """Apply structured published thresholds without inspecting authored text.

    Evaluation-only, revoked, superseded, or withheld policies can never admit a
    diagnostic. Published policies require an exact evaluated profile and exact
    criterion identity for the candidate kind. Mandatory preservation floors are
    conjunctive: a high average cannot compensate for a failed criterion.
    """
    if policy.status != "published" or policy.publish_decision != "publish":
        return "withhold"

    matching_profile = next(
        (
            profile
            for profile in policy.approved_profiles
            if language_tag in profile.language_tags
            and review_mode in profile.review_modes
            and candidate_model_profile_id == profile.candidate_model_profile_id
            and candidate_provider_id == profile.candidate_provider_id
            and judge_model_profile_id == profile.judge_model_profile_id
            and judge_provider_id == profile.judge_provider_id
            and rubric_version == profile.rubric_version
        ),
        None,
    )
    if matching_profile is None:
        return "unsupported_profile"

    if (
        candidate_model_profile_id == judge_model_profile_id
        and not matching_profile.same_model_allowed
    ):
        return "adjudicate"

    if candidate_kind not in _CANDIDATE_KINDS:
        raise EmailWritingPolicyError("candidate_kind_invalid")

    required_criterion_ids = tuple(
        policy.required_criteria_by_candidate_kind[candidate_kind]
    )
    required_set = set(required_criterion_ids)
    if (
        set(criterion_categories) != required_set
        or set(criterion_scores) != required_set
    ):
        raise EmailWritingPolicyError("criterion_identity_mismatch")

    for criterion_id in required_criterion_ids:
        category = criterion_categories[criterion_id]
        score = criterion_scores[criterion_id]
        if type(category) is not int:
            raise EmailWritingPolicyError("criterion_category_invalid")
        if category < 0 or category >= policy.category_count:
            raise EmailWritingPolicyError("criterion_category_invalid")
        if type(score) not in {int, float} or type(score) is bool:
            raise EmailWritingPolicyError("criterion_score_invalid")
        numeric_score = float(score)
        if (
            numeric_score != numeric_score
            or numeric_score in {float("inf"), float("-inf")}
            or not 0.0 <= numeric_score <= 1.0
        ):
            raise EmailWritingPolicyError("criterion_score_invalid")
        if category < policy.mandatory_criterion_floors[criterion_id]:
            return "withhold"
        if numeric_score < policy.minimum_criterion_scores[criterion_id]:
            return "withhold"

    return "admit"


def select_rollback_policy(
    *,
    current_policy: EmailWritingJudgePolicy,
    candidates: Sequence[EmailWritingJudgePolicy],
) -> EmailWritingJudgePolicy:
    """Select only the explicitly named compatible published rollback policy."""
    rollback_version = current_policy.rollback_version
    if rollback_version is None:
        raise EmailWritingPolicyError("policy_rollback_unavailable")
    matches = [
        candidate
        for candidate in candidates
        if candidate.policy_version == rollback_version
        and candidate.status == "published"
        and candidate.publish_decision == "publish"
        and candidate.compatible_contracts == current_policy.compatible_contracts
        and bool(candidate._artifact_name)
        and bool(candidate._artifact_sha256)
    ]
    if len(matches) != 1:
        raise EmailWritingPolicyError("policy_rollback_unavailable")
    return matches[0]
