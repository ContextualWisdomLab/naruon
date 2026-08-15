"""Optimization-safety regression for the GitHub Actions registry audit."""

from __future__ import annotations

import ast
import inspect

from services import github_actions_registry_audit


def test_registry_audit_production_code_has_no_assert_statements() -> None:
    """Production audit controls must remain active when Python runs with ``-O``."""
    source = inspect.getsource(github_actions_registry_audit)
    tree = ast.parse(source)
    assertion_lines = sorted(
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)
    )

    assert assertion_lines == [], (
        "production assertions are removed by optimized Python; found lines "
        f"{assertion_lines}"
    )
