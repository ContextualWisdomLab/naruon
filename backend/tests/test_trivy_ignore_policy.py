"""Regression tests for narrowly scoped Trivy vulnerability suppressions."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIVY_CONFIG = REPO_ROOT / "trivy.yaml"
TRIVY_IGNORE_YAML = REPO_ROOT / ".trivyignore.yaml"
LEGACY_TRIVY_IGNORE = REPO_ROOT / ".trivyignore"
MAX_EXCEPTION_DAYS = 14
NANOID_CVE = "CVE-2026-67213"
NANOID_LOCK_PATH = "frontend/pnpm-lock.yaml"
NANOID_PURL = "pkg:npm/nanoid@3.3.16"


def _parse_vulnerability_blocks(text: str) -> list[list[str]]:
    """Split the controlled Trivy YAML vulnerability list without a YAML dependency."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    in_vulnerabilities = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 0:
            if stripped == "vulnerabilities:":
                in_vulnerabilities = True
                continue
            if in_vulnerabilities:
                break
            continue
        if not in_vulnerabilities:
            continue
        if indent == 2 and stripped.startswith("- id: "):
            if current is not None:
                blocks.append(current)
            current = [raw_line]
            continue
        if current is not None:
            current.append(raw_line)

    if current is not None:
        blocks.append(current)
    return blocks


def _exception_id(block: list[str]) -> str:
    """Return the vulnerability ID from one controlled ignore entry."""
    match = re.fullmatch(r"  - id: (\S+)", block[0])
    assert match is not None, f"invalid Trivy vulnerability entry header: {block[0]!r}"
    return match.group(1)


def _scalar(block: list[str], key: str) -> str:
    """Return a four-space-indented scalar from one controlled ignore entry."""
    prefix = f"    {key}:"
    for raw_line in block[1:]:
        if raw_line.startswith(prefix):
            return raw_line.removeprefix(prefix).strip().strip('"')
    raise AssertionError(f"Trivy exception is missing {key!r}: {block!r}")


def _list_values(block: list[str], key: str) -> list[str]:
    """Return a six-space-indented list belonging to the requested entry key."""
    marker = f"    {key}:"
    for index, raw_line in enumerate(block[1:], start=1):
        if raw_line.strip() != f"{key}:":
            continue
        values: list[str] = []
        for child in block[index + 1 :]:
            if not child.startswith("      - "):
                break
            values.append(child.removeprefix("      - ").strip().strip('"'))
        assert values, f"Trivy exception list {key!r} must not be empty"
        return values
    raise AssertionError(f"Trivy exception is missing scoped list {marker!r}")


def _statement(block: list[str]) -> str:
    """Return the folded statement text for one controlled ignore entry."""
    for index, raw_line in enumerate(block[1:], start=1):
        if raw_line.strip() != "statement: >-":
            continue
        lines: list[str] = []
        for child in block[index + 1 :]:
            if not child.startswith("      "):
                break
            lines.append(child.strip())
        statement = " ".join(lines).strip()
        assert statement, "Trivy exception statement must not be empty"
        return statement
    raise AssertionError("Trivy exception must use a non-empty folded statement")


def test_trivy_vulnerability_exceptions_are_scoped_documented_and_time_bounded() -> None:
    """Reject global, permanent, undocumented, or package-unbound vulnerability ignores."""
    assert not LEGACY_TRIVY_IGNORE.exists(), (
        "legacy .trivyignore suppresses by vulnerability ID globally; use scoped YAML instead"
    )

    config_text = TRIVY_CONFIG.read_text(encoding="utf-8")
    if not TRIVY_IGNORE_YAML.exists():
        assert "ignorefile:" not in config_text, "remove stale ignorefile configuration"
        return

    assert 'ignorefile: ".trivyignore.yaml"' in config_text
    blocks = _parse_vulnerability_blocks(TRIVY_IGNORE_YAML.read_text(encoding="utf-8"))
    assert blocks, "an empty .trivyignore.yaml should be removed instead of retained"

    today = date.today()
    latest_allowed = today + timedelta(days=MAX_EXCEPTION_DAYS)
    for block in blocks:
        vulnerability_id = _exception_id(block)
        assert re.fullmatch(r"CVE-\d{4}-\d+", vulnerability_id)

        paths = _list_values(block, "paths")
        purls = _list_values(block, "purls")
        assert all(path not in {".", "/"} and "*" not in path for path in paths)
        assert all(purl.startswith("pkg:") and "*" not in purl for purl in purls)

        expires = date.fromisoformat(_scalar(block, "expired_at"))
        assert today <= expires <= latest_allowed, (
            f"Trivy exception must expire within {MAX_EXCEPTION_DAYS} days: {vulnerability_id}"
        )
        statement = _statement(block)

        if vulnerability_id == NANOID_CVE:
            assert paths == [NANOID_LOCK_PATH]
            assert purls == [NANOID_PURL]
            assert "nanoid 3.3.16" in statement
            assert "3.3.17" in statement
            assert "npm" in statement.lower()
            assert "Remove this exception" in statement


def test_trivy_exception_parser_keeps_scope_bound_to_each_rule() -> None:
    """Keep package/path scope and rationale attached to the correct exception."""
    text = """vulnerabilities:
  - id: CVE-2026-11111
    paths:
      - frontend/one.lock
    purls:
      - pkg:npm/example@1.0.0
    expired_at: 2026-08-16
    statement: >-
      first rationale
  - id: CVE-2026-22222
    paths:
      - frontend/two.lock
    purls:
      - pkg:npm/other@2.0.0
    expired_at: 2026-08-16
    statement: >-
      second rationale
"""

    blocks = _parse_vulnerability_blocks(text)

    assert [_exception_id(block) for block in blocks] == [
        "CVE-2026-11111",
        "CVE-2026-22222",
    ]
    assert _list_values(blocks[0], "paths") == ["frontend/one.lock"]
    assert _list_values(blocks[1], "purls") == ["pkg:npm/other@2.0.0"]
    assert _statement(blocks[0]) == "first rationale"
    assert _statement(blocks[1]) == "second rationale"
