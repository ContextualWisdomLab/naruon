"""Contract tests for PyPI release-hash provenance of Python lock files.

The network-backed validator is a second, stacked supply-chain boundary after the
offline declaration validator. Tests inject release metadata so normal unit tests
remain deterministic and never depend on public network availability.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "python_lock_registry_provenance.py"

_spec = importlib.util.spec_from_file_location(
    "python_lock_registry_provenance", SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None
registry_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = registry_provenance
_spec.loader.exec_module(registry_provenance)


def _sha(character: str) -> str:
    """Return one syntactically valid SHA-256 digest for fixtures."""
    return character * 64


def _write_lock(path: Path, *, digest: str, version: str = "1.0") -> Path:
    """Write one exact hash-pinned requirement and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"example=={version} \\\n    --hash=sha256:{digest}\n",
        encoding="utf-8",
    )
    return path


def _release_metadata(
    *,
    digest: str,
    version: str = "1.0",
    yanked: bool = False,
    package_type: str = "bdist_wheel",
) -> dict[str, object]:
    """Return a minimal PyPI release JSON payload with one artifact."""
    return {
        "info": {"name": "example", "version": version},
        "urls": [
            {
                "filename": f"example-{version}-py3-none-any.whl",
                "packagetype": package_type,
                "yanked": yanked,
                "digests": {"sha256": digest},
                "url": "https://files.pythonhosted.org/private-looking-path.whl",
            }
        ],
    }


def _codes(receipt: dict[str, object]) -> set[str]:
    """Return stable violation codes from a registry provenance receipt."""
    violations = receipt["violations"]
    assert isinstance(violations, list)
    return {str(item["code"]) for item in violations}


def test_matching_non_yanked_registry_artifact_hash_passes(tmp_path: Path) -> None:
    """A lock hash is accepted only when PyPI publishes it for the exact release."""
    digest = _sha("a")
    lock_path = _write_lock(tmp_path / "requirements-hashes.txt", digest=digest)

    receipt = registry_provenance.validate_lock_against_registry(
        lock_path,
        tmp_path,
        fetch_release=lambda project, version: _release_metadata(
            digest=digest, version=version
        ),
    )

    assert receipt["status"] == "passed"
    assert receipt["path"] == "requirements-hashes.txt"
    assert receipt["requirements"] == [
        {
            "project": "example",
            "version": "1.0",
            "status": "passed",
            "matched_artifact_count": 1,
        }
    ]
    assert receipt["violations"] == []
    assert "pythonhosted" not in json.dumps(receipt, sort_keys=True)


def test_stale_lock_hash_fails_with_stable_code(tmp_path: Path) -> None:
    """A syntactically valid but non-registry SHA-256 cannot attest a release."""
    lock_path = _write_lock(
        tmp_path / "requirements-hashes.txt", digest=_sha("a")
    )

    receipt = registry_provenance.validate_lock_against_registry(
        lock_path,
        tmp_path,
        fetch_release=lambda project, version: _release_metadata(
            digest=_sha("b"), version=version
        ),
    )

    assert receipt["status"] == "failed"
    assert _codes(receipt) == {"registry-hash-mismatch"}


def test_yanked_or_unknown_artifacts_do_not_satisfy_provenance(
    tmp_path: Path,
) -> None:
    """Only non-yanked wheel/sdist artifacts are eligible provenance evidence."""
    digest = _sha("c")
    lock_path = _write_lock(tmp_path / "requirements-hashes.txt", digest=digest)
    metadata = {
        "info": {"name": "example", "version": "1.0"},
        "urls": [
            _release_metadata(digest=digest, yanked=True)["urls"][0],
            _release_metadata(digest=digest, package_type="unknown")["urls"][0],
        ],
    }

    receipt = registry_provenance.validate_lock_against_registry(
        lock_path,
        tmp_path,
        fetch_release=lambda project, version: metadata,
    )

    assert receipt["status"] == "failed"
    assert _codes(receipt) == {"registry-release-has-no-allowed-artifacts"}


def test_release_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    """Metadata for another project or version cannot satisfy the requested pin."""
    digest = _sha("d")
    lock_path = _write_lock(tmp_path / "requirements-hashes.txt", digest=digest)
    metadata = _release_metadata(digest=digest)
    metadata["info"] = {"name": "other-project", "version": "9.9"}

    receipt = registry_provenance.validate_lock_against_registry(
        lock_path,
        tmp_path,
        fetch_release=lambda project, version: metadata,
    )

    assert receipt["status"] == "failed"
    assert _codes(receipt) == {
        "registry-project-mismatch",
        "registry-version-mismatch",
    }


def test_registry_fetch_failure_does_not_serialize_provider_details(
    tmp_path: Path,
) -> None:
    """Transient provider errors fail closed without copying exception text to CI."""
    lock_path = _write_lock(
        tmp_path / "requirements-hashes.txt", digest=_sha("e")
    )

    def failing_fetch(project: str, version: str) -> dict[str, object]:
        raise RuntimeError("SECRET_TOKEN=https://private.invalid/token")

    receipt = registry_provenance.validate_lock_against_registry(
        lock_path,
        tmp_path,
        fetch_release=failing_fetch,
    )
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["status"] == "failed"
    assert _codes(receipt) == {"registry-metadata-fetch-failed"}
    assert "SECRET_TOKEN" not in serialized
    assert "private.invalid" not in serialized


def test_repository_registry_receipt_deduplicates_release_fetches(
    tmp_path: Path,
) -> None:
    """The same project/version across multiple locks is resolved only once."""
    digest = _sha("f")
    _write_lock(tmp_path / "backend" / "requirements-hashes.txt", digest=digest)
    _write_lock(tmp_path / "connector" / "requirements-hashes.txt", digest=digest)
    calls: list[tuple[str, str]] = []

    def fetch_release(project: str, version: str) -> dict[str, object]:
        calls.append((project, version))
        return _release_metadata(digest=digest, version=version)

    receipt = registry_provenance.validate_repository_registry(
        tmp_path,
        fetch_release=fetch_release,
    )

    assert receipt["status"] == "passed"
    assert calls == [("example", "1.0")]
    assert [item["path"] for item in receipt["lock_files"]] == [
        "backend/requirements-hashes.txt",
        "connector/requirements-hashes.txt",
    ]
    assert receipt["schema_version"] == "naruon.python-lock-registry-provenance.v1"


def test_pypi_release_fetch_contract_rejects_untrusted_origin() -> None:
    """The built-in network client only accepts credential-free HTTPS PyPI."""
    for origin in (
        "http://pypi.org",
        "https://user:secret@pypi.org",
        "https://example.invalid",
        "https://pypi.org/path",
        "https://pypi.org?token=secret",
    ):
        with pytest.raises(ValueError, match="trusted PyPI origin"):
            registry_provenance.build_pypi_release_url(
                "example", "1.0", pypi_origin=origin
            )

    assert registry_provenance.build_pypi_release_url("Example_Pkg", "1.0") == (
        "https://pypi.org/pypi/example-pkg/1.0/json"
    )


def test_application_ci_runs_registry_provenance_before_dependency_install() -> None:
    """Application CI must publish registry evidence before installing backend code."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "app-ci.yml").read_text(
            encoding="utf-8"
        )
    )
    backend_job = workflow["jobs"]["backend"]
    steps = backend_job["steps"]
    names = [step.get("name") for step in steps]
    registry_index = names.index("Validate PyPI release hash provenance")
    install_index = names.index("Install backend dependencies")
    assert registry_index < install_index

    registry_step = steps[registry_index]
    command = registry_step["run"]
    assert "python scripts/ci/python_lock_registry_provenance.py --json" in command
    assert "GITHUB_STEP_SUMMARY" in command
    assert 'exit "$status"' in command
