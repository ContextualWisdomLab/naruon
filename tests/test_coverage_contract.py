"""Tests for the repository-root coverage contract."""

from coverage_contract.contract import describe_scope


def test_describe_scope_matches_root_contract() -> None:
    """Keep the root coverage target aligned with the tracked contract files."""

    assert describe_scope() == ("coverage_contract", "tests/test_coverage_contract.py")
