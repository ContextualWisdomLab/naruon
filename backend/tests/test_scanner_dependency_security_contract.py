"""Security floors for the separately installed Strix CI dependency graph.

These source contracts do not execute scanners, providers, or network calls.
The hash lock, not the application's separate runtime lock, feeds Strix CI.
"""

from pathlib import Path
import re

import pytest
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("package", "minimum"),
    [("aiohttp", "3.14.3"), ("pyjwt", "2.15.0"),
     ("urllib3", "2.8.0"), ("litellm", "1.89.7")],
)
def test_scanner_hash_lock_rejects_known_vulnerable_versions(package, minimum):
    """Require patched resolved artifacts, including transitive dependencies."""
    text = (ROOT / "requirements-strix-ci-hashes.txt").read_text(encoding="utf-8")
    records = re.findall(
        r"^([A-Za-z0-9_.-]+)==([^\s\\;]+)([^\n]*(?:\n[ \t]+[^\n]*)*)",
        text, re.MULTILINE,
    )
    matches = [(version, body) for name, version, body in records
               if name.lower().replace("_", "-") == package]
    assert len(matches) == 1, f"expected one exact scanner pin for {package}"
    version, body = matches[0]
    parsed = Version(version)
    assert not parsed.is_prerelease and not parsed.is_devrelease
    assert parsed >= Version(minimum), f"{package}=={version} is below patched floor {minimum}"
    if package == "litellm":
        # GHSA-3cv6-jpf6-8222 has separate maintenance-series patches;
        # a numeric >=1.89.7 check alone would admit vulnerable 1.90.0.
        for introduced, fixed in (
            ("1.90.0", "1.90.7"), ("1.91.0", "1.91.5"),
            ("1.92.0", "1.92.2"), ("1.93.0", "1.93.2"),
            ("1.94.0", "1.94.3"), ("1.95.0", "1.95.1"),
            ("1.96.0", "1.96.2"),
        ):
            assert not Version(introduced) <= parsed < Version(fixed), (
                f"litellm=={version} remains in an affected maintenance series"
            )
    assert re.search(r"--hash=sha256:[0-9a-f]{64}(?=\s|$)", body), package
