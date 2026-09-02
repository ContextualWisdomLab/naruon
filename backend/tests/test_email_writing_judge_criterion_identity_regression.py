"""Regression for the canonical email-writing Judge actionability criterion."""

from __future__ import annotations

from services.email_writing_judge import EMAIL_WRITING_JUDGE_CRITERION_IDS


def test_judge_uses_canonical_actionability_criterion_identity() -> None:
    """Keep Task 7 aligned with ADR-0005 and downstream calibration contracts."""
    assert "actionability" in EMAIL_WRITING_JUDGE_CRITERION_IDS
    assert "actionability_support" not in EMAIL_WRITING_JUDGE_CRITERION_IDS
