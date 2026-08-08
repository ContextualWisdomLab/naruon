"""Regression tests for temporary Trivy vulnerability suppressions."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIVY_IGNORE = REPO_ROOT / ".trivyignore"
MAX_EXCEPTION_DAYS = 14
NANOID_CVE = "CVE-2026-67213"


def test_trivy_vulnerability_exceptions_are_documented_and_time_bounded() -> None:
    """Reject permanent or undocumented vulnerability suppressions."""
    if not TRIVY_IGNORE.exists():
        return

    text = TRIVY_IGNORE.read_text(encoding="utf-8")
    rules = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert rules, "an empty .trivyignore should be removed instead of retained"

    today = date.today()
    latest_allowed = today + timedelta(days=MAX_EXCEPTION_DAYS)
    rule_ids: set[str] = set()
    for rule in rules:
        match = re.fullmatch(r"(CVE-\d{4}-\d+) exp:(\d{4}-\d{2}-\d{2})", rule)
        assert match is not None, f"Trivy exception must expire: {rule!r}"
        rule_ids.add(match.group(1))
        expires = date.fromisoformat(match.group(2))
        assert today <= expires <= latest_allowed, (
            f"Trivy exception must expire within {MAX_EXCEPTION_DAYS} days: {rule!r}"
        )

    if NANOID_CVE in rule_ids:
        assert "nanoid 3.3.16" in text
        assert "3.3.17" in text
        assert "npm" in text.lower()
        assert "Remove this exception" in text


def test_trivy_exception_parser_binds_documentation_to_each_rule() -> None:
    """Keep each exception's rationale attached to only that exception."""
    text = """# first rationale\nCVE-2026-11111 exp:2026-08-16\n\nCVE-2026-22222 exp:2026-08-16\n"""

    exceptions = _parse_trivy_exceptions(text)

    assert exceptions == [
        ("CVE-2026-11111 exp:2026-08-16", ["first rationale"]),
        ("CVE-2026-22222 exp:2026-08-16", []),
    ]
