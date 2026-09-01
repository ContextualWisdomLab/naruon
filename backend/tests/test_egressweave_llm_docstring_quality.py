"""AST-based documentation quality contract for the Naruon EgressWeave adapter."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ADAPTER_PATH = Path(__file__).parents[1] / "services" / "egressweave_llm_adapter.py"
_MINIMUM_WORD_COUNT = 12
_VACUOUS_PREFIXES = (
    "create ",
    "get ",
    "handle ",
    "make ",
    "process ",
    "return ",
    "set ",
)


def _docstring_quality_error(node: ast.AST) -> str | None:
    """Return a deterministic reason when a production docstring is inadequate.

    The checker rejects missing, single-line, and signature-paraphrase prose so
    presence alone cannot satisfy the shipped-code documentation contract.
    """
    docstring = ast.get_docstring(node, clean=True)
    if not docstring:
        return "missing"

    meaningful_lines = [line.strip() for line in docstring.splitlines() if line.strip()]
    if len(meaningful_lines) < 2:
        return "single-line"

    normalized = " ".join(meaningful_lines).strip().lower()
    if len(normalized.split()) < _MINIMUM_WORD_COUNT:
        return "vacuous"
    if normalized.startswith(_VACUOUS_PREFIXES):
        first_line_words = meaningful_lines[0].rstrip(".").split()
        if len(first_line_words) <= 6:
            return "vacuous"
    return None


def _production_definitions(tree: ast.AST) -> list[tuple[str, ast.AST]]:
    """Collect shipped module, class, function, method, and property definitions.

    Nested definitions are included because runtime behavior may live behind an
    internal helper even when that helper is not part of the public API surface.
    """
    definitions: list[tuple[str, ast.AST]] = [("<module>", tree)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append((getattr(node, "name", "<anonymous>"), node))
    return definitions


@pytest.mark.parametrize(
    ("source", "expected_reason"),
    [
        ("def sample():\n    pass\n", "missing"),
        ('def sample():\n    """Return the sample."""\n', "single-line"),
        (
            'def sample():\n    """Return the sample.\n\n    Return the sample unchanged.\n    """\n',
            "vacuous",
        ),
    ],
)
def test_docstring_checker_fails_closed(source: str, expected_reason: str) -> None:
    """Keep the quality checker itself fail-closed for known weak documentation.

    These fixtures prevent a later simplification from silently accepting absent,
    one-line, or content-free docstrings merely to make the production gate pass.
    """
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    assert _docstring_quality_error(function) == expected_reason


def test_egressweave_llm_adapter_has_meaningful_production_docstrings() -> None:
    """Require meaningful documentation on every shipped definition in the adapter.

    The EgressWeave boundary carries SSRF and provider-authority semantics, so each
    definition must document responsibility and constraints rather than only exist.
    """
    tree = ast.parse(_ADAPTER_PATH.read_text(encoding="utf-8"), filename=str(_ADAPTER_PATH))
    violations = [
        f"{name}: {reason}"
        for name, node in _production_definitions(tree)
        if (reason := _docstring_quality_error(node)) is not None
    ]
    assert violations == [], "production docstring quality violations: " + ", ".join(violations)
