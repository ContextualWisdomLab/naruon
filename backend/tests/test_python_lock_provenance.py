"""Contract tests for deterministic Python lock provenance receipts.

The validator is intentionally exercised from backend CI because hash-locked
requirements are part of the release supply-chain boundary rather than an
optional developer convenience.
"""

from __future__ import annotations

import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "python_lock_provenance.py"

_spec = importlib.util.spec_from_file_location("python_lock_provenance", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
python_lock_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = python_lock_provenance
_spec.loader.exec_module(python_lock_provenance)


def _write(path: Path, text: str) -> Path:
    """Create one UTF-8 fixture file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sha(character: str = "a") -> str:
    """Return one syntactically valid SHA-256 hex digest for fixtures."""
    return character * 64


def _violation_codes(receipt: dict[str, object]) -> set[str]:
    """Return stable violation codes from one lock receipt."""
    violations = receipt["violations"]
    assert isinstance(violations, list)
    return {str(item["code"]) for item in violations}


def _simple_lock(name: str = "example", version: str = "1.0") -> str:
    """Return one exact hash-pinned requirement fixture."""
    return f"{name}=={version} \\\n    --hash=sha256:{_sha()}\n"


def test_manual_download_generation_version_mismatch_is_rejected(tmp_path: Path) -> None:
    """A stale generator command must not attest a newer declared package."""
    lock_path = _write(
        tmp_path / "connector" / "requirements-hashes.txt",
        "# Regenerate with:\n"
        "#   python3 -m pip download --only-binary=:all: websockets==16.1\n"
        "websockets==17.0 \\\n"
        f"    --hash=sha256:{_sha()}\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"generation-version-mismatch"}


def test_manual_download_generation_matching_version_passes(tmp_path: Path) -> None:
    """A matching manual generator command and SHA-256 pin form a valid declaration."""
    lock_path = _write(
        tmp_path / "connector" / "requirements-hashes.txt",
        "# Regenerate with:\n"
        "#   python3 -m pip download --only-binary=:all: websockets==17.0\n"
        "websockets==17.0 \\\n"
        f"    --hash=sha256:{_sha('b')}\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "passed"
    assert receipt["violations"] == []
    assert receipt["requirement_count"] == 1
    assert receipt["sha256_hash_count"] == 1
    assert receipt["generation_mode"] == "pip-download"


def test_manual_download_generation_with_extras_passes(tmp_path: Path) -> None:
    """PEP 508 extras remain bound to the same normalized project/version pin."""
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# Regenerate with:\n"
        "#   python3 -m pip download 'SomePackage[PDF]==3.0'\n"
        "SomePackage[PDF]==3.0 \\\n"
        f"    --hash=sha256:{_sha('d')}\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "passed"
    assert receipt["generation_mode"] == "pip-download"
    assert receipt["violations"] == []


def test_manual_download_without_exact_generator_pin_is_rejected(tmp_path: Path) -> None:
    """A recognized manual generator must name the package/version it attests."""
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# Regenerate with:\n"
        "#   python3 -m pip download --only-binary=:all:\n"
        + _simple_lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"generation-input-missing"}


def test_unpinned_and_unhashed_requirements_fail_closed(tmp_path: Path) -> None:
    """Hash-checking evidence rejects non-exact pins and missing SHA-256 hashes."""
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "example>=1.0\n"
        "other==2.0\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {
        "missing-sha256",
        "requirement-not-exactly-pinned",
    }


def test_malformed_orphan_and_duplicate_hash_evidence_is_rejected(tmp_path: Path) -> None:
    """Malformed hash structure fails with stable, independently useful codes."""
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        f"--hash=sha256:{_sha('a')}\n"
        "example==1.0 \\\n"
        "    --hash=sha256:not-a-digest\n"
        "example==1.0 \\\n"
        f"    --hash=sha256:{_sha('b')}\n"
        "--hash=sha512:not-supported\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {
        "duplicate-requirement",
        "malformed-sha256",
        "missing-sha256",
        "orphan-hash",
    }


def test_uv_generation_source_version_mismatch_is_rejected(tmp_path: Path) -> None:
    """A uv-generated lock must agree with exact direct pins in its declared input."""
    _write(
        tmp_path / "requirements.txt",
        "# direct dependencies\n--index-url https://example.invalid/simple\n"
        "ignored>=1\nexample==2.0\n",
    )
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# This file was autogenerated by uv via the following command:\n"
        "#    uv pip compile --generate-hashes --output-file requirements-hashes.txt requirements.txt\n"
        "example==1.0 \\\n"
        f"    --hash=sha256:{_sha('c')}\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"generation-version-mismatch"}


def test_uv_generation_accepts_requirements_in_source(tmp_path: Path) -> None:
    """The conventional requirements.in source form is valid uv provenance."""
    _write(tmp_path / "requirements.in", "example==1.0\n")
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# uv pip compile requirements.in --generate-hashes --output-file requirements-hashes.txt\n"
        + _simple_lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "passed"
    assert receipt["generation_mode"] == "uv"
    assert receipt["violations"] == []


def test_uv_generation_missing_input_is_rejected(tmp_path: Path) -> None:
    """A generated lock cannot claim provenance from a source file that is absent."""
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# This file was autogenerated by uv via the following command:\n"
        "#    uv pip compile --generate-hashes --output-file requirements-hashes.txt requirements.txt\n"
        + _simple_lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"generation-input-missing"}


def test_uv_generation_requires_output_and_source_declarations(tmp_path: Path) -> None:
    """A uv command must bind both its output lock and input requirements path."""
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# uv pip compile --generate-hashes\n" + _simple_lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {
        "generation-input-missing",
        "generation-output-missing",
    }


def test_uv_generation_output_path_mismatch_is_rejected(tmp_path: Path) -> None:
    """A generator cannot attest a different lock path than the file under test."""
    _write(tmp_path / "requirements.txt", "example==1.0\n")
    lock_path = _write(
        tmp_path / "requirements-hashes.txt",
        "# uv pip compile --generate-hashes --output-file other-hashes.txt requirements.txt\n"
        + _simple_lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, tmp_path)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"generation-output-mismatch"}


def test_uv_generation_rejects_source_outside_repository(tmp_path: Path) -> None:
    """A generator declaration cannot make CI read a source outside the repo."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _write(tmp_path / "outside" / "requirements.in", "external-secret==9.9\n")
    lock_path = _write(
        repository_root / "requirements-hashes.txt",
        "# uv pip compile ../outside/requirements.in --output-file requirements-hashes.txt\n"
        + _simple_lock(),
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, repository_root)
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"generation-input-outside-repository"}
    assert "external-secret" not in serialized
    assert str(tmp_path) not in serialized


def test_repository_receipt_covers_every_active_hash_lock() -> None:
    """The current repository must expose one passing receipt for every active lock."""
    receipt = python_lock_provenance.validate_repository(REPO_ROOT)
    lock_files = receipt["lock_files"]
    assert isinstance(lock_files, list)
    paths = {str(item["path"]) for item in lock_files}

    assert receipt["status"] == "passed"
    assert paths == {
        "backend/requirements-agent.txt",
        "backend/requirements-hashes.txt",
        "connector/requirements-hashes.txt",
        "requirements-bandit-ci-hashes.txt",
        "requirements-strix-ci-hashes.txt",
    }
    assert all(len(str(item["sha256"])) == 64 for item in lock_files)
    assert receipt["violations"] == []


def test_repository_receipt_is_deterministic_and_path_relative(tmp_path: Path) -> None:
    """Machine evidence is stable and never leaks an absolute runner path."""
    _write(tmp_path / "requirements-hashes.txt", _simple_lock())
    _write(tmp_path / "requirements.txt", "example==1.0\n")
    _write(tmp_path / "notes.txt", "not a requirements file\n")
    _write(tmp_path / ".venv" / "requirements-hidden.txt", _simple_lock())
    (tmp_path / "requirements-binary.txt").write_bytes(b"\xff\xfe\x00")

    first = python_lock_provenance.validate_repository(tmp_path)
    second = python_lock_provenance.validate_repository(tmp_path)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    serialized = json.dumps(first, sort_keys=True)
    assert str(tmp_path) not in serialized
    assert first["schema_version"] == "naruon.python-lock-provenance.v1"
    assert [item["path"] for item in first["lock_files"]] == [
        "requirements-hashes.txt"
    ]


def test_outside_repository_lock_fails_without_reading_payload(tmp_path: Path) -> None:
    """Direct validation rejects an out-of-root lock without serializing its data."""
    root = tmp_path / "root"
    root.mkdir()
    lock_path = _write(
        tmp_path / "outside" / "requirements-hashes.txt",
        "TOP_SECRET_PACKAGE>=9.9\n",
    )

    receipt = python_lock_provenance.validate_lock_file(lock_path, root)
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["status"] == "failed"
    assert receipt["path"] == "requirements-hashes.txt"
    assert _violation_codes(receipt) == {"lock-path-outside-repository"}
    assert "TOP_SECRET_PACKAGE" not in serialized
    assert str(tmp_path) not in serialized


def test_discovery_rejects_symlinked_lock_outside_repository(tmp_path: Path) -> None:
    """Repository discovery never follows a requirements symlink outside root."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    outside_lock = _write(
        tmp_path / "outside" / "secret.txt",
        "TOP_SECRET_PACKAGE>=9.9\n",
    )
    (repository_root / "requirements-hashes.txt").symlink_to(outside_lock)

    receipt = python_lock_provenance.validate_repository(repository_root)
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["status"] == "failed"
    assert _violation_codes(receipt) == {"lock-path-outside-repository"}
    assert "TOP_SECRET_PACKAGE" not in serialized
    assert str(tmp_path) not in serialized


def test_cli_json_and_human_modes_report_pass_and_fail(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both operator surfaces preserve exit status and actionable reason codes."""
    _write(tmp_path / "requirements-hashes.txt", _simple_lock())
    assert python_lock_provenance.main(["--repository-root", str(tmp_path), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["status"] == "passed"

    _write(tmp_path / "requirements-hashes.txt", "example>=1.0\n")
    assert python_lock_provenance.main(["--repository-root", str(tmp_path)]) == 1
    human_output = capsys.readouterr().out
    assert "Python lock provenance: failed" in human_output
    assert "requirement-not-exactly-pinned" in human_output


def test_script_main_guard_propagates_failed_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct script execution exits nonzero when repository validation fails."""
    _write(tmp_path / "requirements-hashes.txt", "example>=1.0\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "--repository-root", str(tmp_path), "--json"],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 1


def test_application_ci_publishes_lock_provenance_receipt() -> None:
    """The backend install job must publish validation evidence before installation."""
    workflow_path = REPO_ROOT / ".github" / "workflows" / "app-ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    backend_jobs = [
        job
        for job in jobs.values()
        if any(
            step.get("name") == "Install backend dependencies"
            for step in job.get("steps", [])
            if isinstance(step, dict)
        )
    ]
    assert len(backend_jobs) == 1

    steps = backend_jobs[0]["steps"]
    step_names = [step.get("name") for step in steps]
    validation_index = step_names.index("Validate Python lock provenance")
    install_index = step_names.index("Install backend dependencies")
    assert validation_index < install_index

    validation_step = steps[validation_index]
    validation_run = validation_step["run"]
    assert "python scripts/ci/python_lock_provenance.py --json" in validation_run
    assert "GITHUB_STEP_SUMMARY" in validation_run
    assert "|| status=$?" in validation_run
    assert 'exit "$status"' in validation_run
