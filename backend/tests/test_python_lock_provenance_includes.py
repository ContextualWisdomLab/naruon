"""Focused contracts for requirements-file include provenance validation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "python_lock_provenance.py"

_spec = importlib.util.spec_from_file_location(
    "python_lock_provenance_includes", SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None
python_lock_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = python_lock_provenance
_spec.loader.exec_module(python_lock_provenance)


def _write(path: Path, text: str) -> Path:
    """Create one UTF-8 requirements fixture and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sha(character: str = "a") -> str:
    """Return one syntactically valid SHA-256 fixture digest."""
    return character * 64


def _lock(name: str = "root-package", version: str = "1.0") -> str:
    """Return one exact requirement with SHA-256 evidence."""
    return f"{name}=={version} \\\n    --hash=sha256:{_sha()}\n"


def _violation_codes(receipt: dict[str, object]) -> set[str]:
    """Return stable violation codes from one receipt."""
    violations = receipt["violations"]
    assert isinstance(violations, list)
    return {str(item["code"]) for item in violations}


@pytest.mark.parametrize("directive", ["-r", "--requirement"])
def test_requirement_include_forms_are_validated_recursively(
    tmp_path: Path,
    directive: str,
) -> None:
    """Both pip include forms expose invalid included requirements."""
    included_path = _write(
        tmp_path / "backend" / "generated-lock.txt",
        "included-package>=2.0\n",
    )
    root_path = _write(
        tmp_path / "requirements-hashes.txt",
        f"{directive} backend/generated-lock.txt\n" + _lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(root_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {
        "missing-sha256",
        "requirement-not-exactly-pinned",
    }
    assert receipt["requirement_count"] == 1
    assert receipt["sha256_hash_count"] == 1
    included_files = receipt["included_files"]
    assert isinstance(included_files, list)
    assert [item["path"] for item in included_files] == [
        included_path.relative_to(tmp_path).as_posix()
    ]
    assert included_files[0]["sha256"] == hashlib.sha256(
        included_path.read_bytes()
    ).hexdigest()


def test_valid_nested_requirement_include_contributes_receipt_counts(
    tmp_path: Path,
) -> None:
    """A contained valid include is represented and counted deterministically."""
    _write(tmp_path / "nested" / "included-lock.txt", _lock("child-package", "2.0"))
    root_path = _write(
        tmp_path / "requirements-hashes.txt",
        "--requirement=nested/included-lock.txt\n" + _lock(),
    )

    first = python_lock_provenance.validate_lock_file(root_path, tmp_path)
    second = python_lock_provenance.validate_lock_file(root_path, tmp_path)

    assert first["status"] == "passed"
    assert first["requirement_count"] == 2
    assert first["sha256_hash_count"] == 2
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_requirement_include_outside_repository_fails_without_reading_payload(
    tmp_path: Path,
) -> None:
    """An escaping include cannot expose external file content or absolute paths."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _write(
        tmp_path / "outside" / "generated-lock.txt",
        "EXTERNAL_SECRET_PACKAGE>=9.9\n",
    )
    root_path = _write(
        repository_root / "requirements-hashes.txt",
        "-r ../outside/generated-lock.txt\n" + _lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(root_path, repository_root)
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {
        "requirement-include-outside-repository"
    }
    assert "EXTERNAL_SECRET_PACKAGE" not in serialized
    assert str(tmp_path) not in serialized


def test_missing_requirement_include_fails_closed(tmp_path: Path) -> None:
    """A missing or non-file include has one stable operator-facing reason code."""
    (tmp_path / "missing-lock.txt").mkdir()
    root_path = _write(
        tmp_path / "requirements-hashes.txt",
        "-r missing-lock.txt\n" + _lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(root_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"requirement-include-missing"}


def test_malformed_requirement_include_fails_closed(tmp_path: Path) -> None:
    """An include option without exactly one path cannot be silently skipped."""
    root_path = _write(
        tmp_path / "requirements-hashes.txt",
        "--requirement\n" + _lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(root_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"requirement-include-invalid"}


def test_requirement_include_cycle_fails_closed(tmp_path: Path) -> None:
    """A recursive include cycle terminates with a stable reason code."""
    root_path = _write(
        tmp_path / "requirements-hashes.txt",
        "-r nested/child-lock.txt\n" + _lock(),
    )
    _write(
        tmp_path / "nested" / "child-lock.txt",
        "--requirement ../requirements-hashes.txt\n" + _lock("child-package", "2.0"),
    )

    receipt = python_lock_provenance.validate_lock_file(root_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"requirement-include-cycle"}


def test_requirement_include_depth_is_bounded(tmp_path: Path) -> None:
    """A hostile acyclic include chain cannot exhaust Python recursion."""
    depth = python_lock_provenance._MAX_REQUIREMENT_INCLUDE_DEPTH + 2
    for index in range(depth):
        include = f"-r lock-{index + 1}.txt\n" if index + 1 < depth else ""
        _write(
            tmp_path / f"lock-{index}.txt",
            include + _lock(f"package-{index}", f"{index + 1}.0"),
        )

    receipt = python_lock_provenance.validate_lock_file(
        tmp_path / "lock-0.txt",
        tmp_path,
    )

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {
        "requirement-include-depth-exceeded"
    }
