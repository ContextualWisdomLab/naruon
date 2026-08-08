"""Regression tests for temporary Trivy vulnerability suppressions."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIVY_IGNORE = REPO_ROOT / ".trivyignore"
MAX_EXCEPTION_DAYS = 14


def test_trivy_vulnerability_exceptions_are_documented_and_time_bounded() -> None:
    """Reject permanent or undocumented vulnerability suppressions."""
    assert TRIVY_IGNORE.exists(), "temporary Trivy exceptions must be explicit"
    text = TRIVY_IGNORE.read_text(encoding="utf-8")
    rules = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert rules, "an empty .trivyignore should be removed instead of retained"
    assert "nanoid 3.3.16" in text
    assert "3.3.17" in text
    assert "npm" in text.lower()

    today = date.today()
    latest_allowed = today + timedelta(days=MAX_EXCEPTION_DAYS)
    for rule in rules:
        match = re.fullmatch(r"(CVE-\d{4}-\d+) exp:(\d{4}-\d{2}-\d{2})", rule)
        assert match is not None, f"Trivy exception must expire: {rule!r}"
        expires = date.fromisoformat(match.group(2))
        assert today <= expires <= latest_allowed, (
            f"Trivy exception must expire within {MAX_EXCEPTION_DAYS} days: {rule!r}"
        )
