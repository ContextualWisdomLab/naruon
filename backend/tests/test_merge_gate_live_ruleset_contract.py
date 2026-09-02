from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MERGE_GATE_POLICY = REPOSITORY_ROOT / "docs/development/merge-gate-policy.md"
ROBOT_REVIEW_SKILL = (
    REPOSITORY_ROOT / ".agents/skills/github-robot-review-gate/SKILL.md"
)


def test_merge_gate_guidance_matches_live_one_approval_ruleset() -> None:
    """Operator guidance must not instruct agents to weaken the live review gate."""
    policy = MERGE_GATE_POLICY.read_text(encoding="utf-8")
    skill = ROBOT_REVIEW_SKILL.read_text(encoding="utf-8")

    for guidance in (policy, skill):
        assert "required_approving_review_count=0" not in guidance
        assert "required_approving_review_count=1" in guidance
        assert "do not lower" in guidance.lower()


def test_robot_evidence_is_not_substituted_for_required_approval() -> None:
    """Robot evidence and the live GitHub approval requirement remain distinct gates."""
    policy = MERGE_GATE_POLICY.read_text(encoding="utf-8")

    assert "one qualifying independent approval" in policy.lower()
    assert "robot-review evidence does not replace" in policy.lower()
