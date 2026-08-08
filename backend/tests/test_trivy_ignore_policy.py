"""Regression tests for temporary Trivy vulnerability suppressions."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIVY_IGNORE = REPO_ROOT / ".trivyignore"
MAX_EXCEPTION_DAYS = 14
NANOID_CVE = "CVE-2026-67213"


def _parse_trivy_exceptions(text: str) -> list[tuple[str, list[str]]]:
    """Bind each non-comment ignore rule to its immediately preceding comments."""
    exceptions: list[tuple[str, list[str]]] = []
    pending_comments: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            pending_comments = []
            continue
        if line.startswith("#"):
            comment = line.removeprefix("#").strip()
            if comment:
                pending_comments.append(comment)
            continue
        exceptions.append((line, pending_comments.copy()))
        pending_comments = []
    return exceptions


def test_trivy_vulnerability_exceptions_are_documented_and_time_bounded() -> None:
    """Reject permanent or undocumented vulnerability suppressions."""
    if not TRIVY_IGNORE.exists():
        return

    text = TRIVY_IGNORE.read_text(encoding="utf-8")
    exceptions = _parse_trivy_exceptions(text)
    assert exceptions, "an empty .trivyignore should be removed instead of retained"

    today = date.today()
    latest_allowed = today + timedelta(days=MAX_EXCEPTION_DAYS)
    for rule, documentation in exceptions:
        assert documentation, f"Trivy exception must document its rationale: {rule!r}"
        match = re.fullmatch(r"(CVE-\d{4}-\d+) exp:(\d{4}-\d{2}-\d{2})", rule)
        assert match is not None, f"Trivy exception must expire: {rule!r}"
        expires = date.fromisoformat(match.group(2))
        assert today <= expires <= latest_allowed, (
            f"Trivy exception must expire within {MAX_EXCEPTION_DAYS} days: {rule!r}"
        )

        if match.group(1) == NANOID_CVE:
            rationale = "\n".join(documentation)
            assert "nanoid 3.3.16" in rationale
            assert "3.3.17" in rationale
            assert "npm" in rationale.lower()
            assert "Remove this exception" in rationale


def test_trivy_exception_parser_binds_documentation_to_each_rule() -> None:
    """Keep each exception's rationale attached to only that exception."""
    text = """# first rationale\nCVE-2026-11111 exp:2026-08-16\n\nCVE-2026-22222 exp:2026-08-16\n"""

    exceptions = _parse_trivy_exceptions(text)

    assert exceptions == [
        ("CVE-2026-11111 exp:2026-08-16", ["first rationale"]),
        ("CVE-2026-22222 exp:2026-08-16", []),
    ]
