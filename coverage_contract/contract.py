"""Small coverage contract used by the OpenCode coverage-evidence workflow."""


def describe_scope() -> tuple[str, str]:
    """Return the Python package and test target used by the coverage contract."""

    return ("coverage_contract", "tests/test_coverage_contract.py")
