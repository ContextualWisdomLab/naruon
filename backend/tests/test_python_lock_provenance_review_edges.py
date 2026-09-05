"""Review regressions for Python lock provenance edge contracts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "ci" / "python_lock_provenance.py"

_spec = importlib.util.spec_from_file_location("python_lock_provenance_edges", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
python_lock_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = python_lock_provenance
_spec.loader.exec_module(python_lock_provenance)


def _hash(character: str) -> str:
    """Return one syntactically valid SHA-256 fixture digest."""
    return character * 64


def _codes(receipt: dict[str, object]) -> set[str]:
    """Return top-level stable violation codes from a lock receipt."""
    violations = receipt["violations"]
    assert isinstance(violations, list)
    return {str(item["code"]) for item in violations}


def test_uv_generation_checks_every_declared_source_file(tmp_path: Path) -> None:
    """A stale pin in an earlier uv input must not escape version agreement."""
    (tmp_path / "first.in").write_text("alpha==1.0\n", encoding="utf-8")
    (tmp_path / "second.in").write_text("beta==2.0\n", encoding="utf-8")
    lock_path = tmp_path / "requirements-hashes.txt"
    lock_path.write_text(
        "# uv pip compile first.in second.in --output-file requirements-hashes.txt\n"
        f"alpha==9.0 \\\n    --hash=sha256:{_hash('a')}\n"
        f"beta==2.0 \\\n    --hash=sha256:{_hash('b')}\n",
        encoding="utf-8",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert "generation-version-mismatch" in _codes(receipt)


def test_non_utf8_requirement_include_returns_stable_failure(tmp_path: Path) -> None:
    """An undecodable included file must fail closed without a Python traceback."""
    lock_path = tmp_path / "requirements-hashes.txt"
    lock_path.write_text("-r binary.in\n", encoding="utf-8")
    (tmp_path / "binary.in").write_bytes(b"\xff\xfe\x00")

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert "lock-read-failed" in _codes(receipt)
