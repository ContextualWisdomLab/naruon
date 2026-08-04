#!/usr/bin/env python3
"""Materialize the cryptography 50 security remediation on its isolated branch.

The script keeps source mutation reviewable and deterministic while the
one-shot GitHub workflow supplies the supported Python runtimes, regenerates
locks, and executes the complete verification matrix.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RELEASE_GOVERNANCE_TEST = REPOSITORY_ROOT / "backend/tests/test_release_governance.py"
CRYPTOGRAPHY_OLD_PIN = "cryptography==49.0.0"
CRYPTOGRAPHY_NEW_PIN = "cryptography==50.0.0"
TEST_NAME = "test_cryptography_runtime_pins_are_bleichenbacher_oracle_fixed"
TEST_SOURCE = '''


def test_cryptography_runtime_pins_are_bleichenbacher_oracle_fixed() -> None:
    """Require every governed Python surface to use the first oracle-safe release."""
    backend_requirements = read_repo_text("backend/requirements.txt")
    backend_project = read_repo_text("backend/pyproject.toml")
    backend_lock = tomllib.loads(read_repo_text("backend/uv.lock"))
    backend_hashes = read_repo_text("backend/requirements-hashes.txt")
    strix_requirements = read_repo_text("requirements-strix-ci.txt")
    strix_hashes = read_repo_text("requirements-strix-ci-hashes.txt")

    governed_text = "\\n".join(
        (
            backend_requirements,
            backend_project,
            backend_hashes,
            strix_requirements,
            strix_hashes,
        )
    )
    assert "cryptography==49.0.0" not in governed_text
    assert "cryptography==50.0.0" in backend_requirements
    assert '"cryptography==50.0.0"' in backend_project
    assert "cryptography==50.0.0" in backend_hashes
    assert "cryptography==50.0.0" in strix_requirements
    assert "cryptography==50.0.0" in strix_hashes
    cryptography_versions = {
        package["version"]
        for package in backend_lock["package"]
        if package["name"] == "cryptography"
    }
    assert cryptography_versions == {"50.0.0"}
'''
CHANGELOG_BULLET = (
    "- `cryptography`를 `50.0.0`으로 갱신해 공격자 제공 PKCS#7 "
    "EnvelopedData 복호화 결과의 오류·타이밍 차이로 발생하는 "
    "Bleichenbacher oracle(`CVE-2026-69247`, `GHSA-g6cj-pr64-35w5`)을 "
    "제거하고, backend·uv lock·hash lock·Strix CI 의존성 증거를 같은 "
    "버전으로 동기화했습니다.\n"
)
CHANGELOG_MARKER = "### 보안 패치 (CodeQL extended current-head)\n\n"


def add_failing_test() -> None:
    """Add the security regression test without changing vulnerable pins."""
    text = RELEASE_GOVERNANCE_TEST.read_text(encoding="utf-8")
    if "import tomllib\n" not in text:
        import_anchor = "import sys\n"
        if text.count(import_anchor) != 1:
            raise RuntimeError("tomllib import anchor was not found exactly once")
        text = text.replace(import_anchor, import_anchor + "import tomllib\n", 1)
    if TEST_NAME not in text:
        text += TEST_SOURCE
    RELEASE_GOVERNANCE_TEST.write_text(text, encoding="utf-8")


def replace_pin(path: Path) -> None:
    """Replace every governed cryptography 49 pin in one text artifact."""
    text = path.read_text(encoding="utf-8")
    if CRYPTOGRAPHY_OLD_PIN not in text:
        raise RuntimeError(f"cryptography 49 pin is missing from {path}")
    path.write_text(
        text.replace(CRYPTOGRAPHY_OLD_PIN, CRYPTOGRAPHY_NEW_PIN),
        encoding="utf-8",
    )


def apply_remediation() -> None:
    """Update governed pins, the regression expectation, and CHANGELOG."""
    for relative_path in (
        "backend/requirements.txt",
        "backend/pyproject.toml",
        "requirements-strix-ci.txt",
        "backend/tests/test_release_governance.py",
    ):
        replace_pin(REPOSITORY_ROOT / relative_path)

    changelog_path = REPOSITORY_ROOT / "CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    if CHANGELOG_BULLET not in changelog:
        if changelog.count(CHANGELOG_MARKER) != 1:
            raise RuntimeError("Unreleased security changelog marker was not found once")
        changelog = changelog.replace(
            CHANGELOG_MARKER,
            CHANGELOG_MARKER + CHANGELOG_BULLET,
            1,
        )
    changelog_path.write_text(changelog, encoding="utf-8")


def main() -> None:
    """Dispatch the requested deterministic materialization phase."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("add-test", "apply"))
    args = parser.parse_args()
    if args.phase == "add-test":
        add_failing_test()
    else:
        apply_remediation()


if __name__ == "__main__":
    main()
