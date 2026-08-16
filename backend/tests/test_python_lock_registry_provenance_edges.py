"""Edge and transport tests for the PyPI lock-provenance validator."""

from __future__ import annotations

import importlib.util
import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "python_lock_registry_provenance.py"
_spec = importlib.util.spec_from_file_location("python_lock_registry_edges", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
registry_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = registry_provenance
_spec.loader.exec_module(registry_provenance)


def _sha(character: str = "a") -> str:
    """Return a fixture SHA-256 digest."""
    return character * 64


def _write(path: Path, text: str) -> Path:
    """Write one UTF-8 fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _codes(receipt: dict[str, object]) -> set[str]:
    """Return stable violation codes from a receipt."""
    return {str(item["code"]) for item in receipt["violations"]}


def _metadata(digest: str) -> dict[str, object]:
    """Return one eligible exact-release metadata fixture."""
    return {
        "info": {"name": "example", "version": "1.0"},
        "urls": [
            {
                "packagetype": "sdist",
                "yanked": False,
                "digests": {"sha256": digest},
            }
        ],
    }


def test_lock_parser_fails_closed_on_structure_errors(tmp_path: Path) -> None:
    """Orphan hashes, non-exact pins, and missing hashes are separately visible."""
    path = _write(
        tmp_path / "requirements-hashes.txt",
        f"--hash=sha256:{_sha()}\nexample>=1\nother==2.0\n",
    )
    receipt = registry_provenance.validate_lock_against_registry(
        path,
        tmp_path,
        fetch_release=lambda project, version: _metadata(_sha("b")),
    )
    assert receipt["status"] == "failed"
    assert {
        "lock-orphan-sha256",
        "lock-requirement-not-exact",
        "lock-requirement-has-no-sha256",
    }.issubset(_codes(receipt))


def test_outside_symlink_is_rejected_without_reading_payload(tmp_path: Path) -> None:
    """A discovered lock symlink cannot exfiltrate an external file."""
    root = tmp_path / "repo"
    root.mkdir()
    outside = _write(tmp_path / "outside.txt", "TOP_SECRET>=1\n")
    (root / "requirements-hashes.txt").symlink_to(outside)
    receipt = registry_provenance.validate_repository_registry(
        root,
        fetch_release=lambda project, version: _metadata(_sha()),
    )
    serialized = json.dumps(receipt, sort_keys=True)
    assert receipt["status"] == "failed"
    assert _codes(receipt["lock_files"][0]) == {"lock-path-outside-repository"}
    assert "TOP_SECRET" not in serialized
    assert str(tmp_path) not in serialized


def test_unreadable_utf8_lock_is_ignored_by_discovery(tmp_path: Path) -> None:
    """Binary requirements candidates are not interpreted as provenance locks."""
    (tmp_path / "requirements-hashes.txt").write_bytes(b"\xff\xfe")
    assert registry_provenance.discover_hash_locks(tmp_path) == []


def test_direct_invalid_utf8_lock_returns_stable_read_failure(tmp_path: Path) -> None:
    """Direct validation reports a generic read failure without raw bytes."""
    path = tmp_path / "requirements-hashes.txt"
    path.write_bytes(b"\xff\xfe")
    receipt = registry_provenance.validate_lock_against_registry(path, tmp_path)
    assert _codes(receipt) == {"lock-read-failed"}
    assert receipt["requirements"] == []


def test_artifact_filter_ignores_malformed_registry_entries() -> None:
    """Only non-yanked wheel/sdist objects with valid SHA-256 values count."""
    assert registry_provenance._eligible_registry_hashes({"urls": "bad"}) == set()
    metadata = {
        "urls": [
            "bad",
            {"packagetype": "sdist", "yanked": True, "digests": {"sha256": _sha()}},
            {"packagetype": "other", "yanked": False, "digests": {"sha256": _sha()}},
            {"packagetype": "sdist", "yanked": False, "digests": "bad"},
            {"packagetype": "sdist", "yanked": False, "digests": {"sha256": "bad"}},
            {"packagetype": "bdist_wheel", "yanked": False, "digests": {"sha256": _sha("c").upper()}},
        ]
    }
    assert registry_provenance._eligible_registry_hashes(metadata) == {_sha("c")}


class _Headers(dict[str, str]):
    """Minimal urllib-compatible response header mapping."""


class _Response:
    """Minimal context-managed urllib response for transport tests."""

    def __init__(self, payload: bytes, content_type: str = "application/json") -> None:
        self.payload = payload
        self.headers = _Headers({"Content-Type": content_type})

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.payload[:size]


def test_fetch_pypi_release_enforces_bounds_and_json_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real transport validates configuration, media type, size, and JSON shape."""
    payload = json.dumps(_metadata(_sha())).encode()
    monkeypatch.setattr(
        registry_provenance.urllib.request,
        "urlopen",
        lambda request, timeout: _Response(payload),
    )
    assert registry_provenance.fetch_pypi_release("example", "1.0")["info"] == {
        "name": "example",
        "version": "1.0",
    }

    for kwargs in ({"timeout_seconds": 0}, {"max_metadata_bytes": 0}):
        with pytest.raises(ValueError):
            registry_provenance.fetch_pypi_release("example", "1.0", **kwargs)

    monkeypatch.setattr(
        registry_provenance.urllib.request,
        "urlopen",
        lambda request, timeout: _Response(payload, "text/plain"),
    )
    with pytest.raises(ValueError, match="must be JSON"):
        registry_provenance.fetch_pypi_release("example", "1.0")

    monkeypatch.setattr(
        registry_provenance.urllib.request,
        "urlopen",
        lambda request, timeout: _Response(b"{}x"),
    )
    with pytest.raises(ValueError, match="byte limit"):
        registry_provenance.fetch_pypi_release(
            "example", "1.0", max_metadata_bytes=2
        )

    monkeypatch.setattr(
        registry_provenance.urllib.request,
        "urlopen",
        lambda request, timeout: _Response(b"[]"),
    )
    with pytest.raises(ValueError, match="JSON object"):
        registry_provenance.fetch_pypi_release("example", "1.0")


def test_origin_validation_rejects_invalid_port_and_fragment() -> None:
    """Malformed authority and fragment-bearing origins fail before network use."""
    for origin in ("https://pypi.org:bad", "https://pypi.org/#fragment"):
        with pytest.raises(ValueError, match="trusted PyPI origin"):
            registry_provenance.build_pypi_release_url(
                "example", "1.0", pypi_origin=origin
            )


def test_cached_registry_failure_is_not_retried_per_lock(tmp_path: Path) -> None:
    """One failed exact release resolution is shared across repeated lock entries."""
    for directory in ("a", "b"):
        _write(
            tmp_path / directory / "requirements-hashes.txt",
            f"example==1.0 \\\n    --hash=sha256:{_sha()}\n",
        )
    calls = 0

    def fail_once(project: str, version: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    receipt = registry_provenance.validate_repository_registry(
        tmp_path,
        fetch_release=fail_once,
    )
    assert calls == 1
    assert receipt["status"] == "failed"
    assert all(
        _codes(lock) == {"registry-metadata-fetch-failed"}
        for lock in receipt["lock_files"]
    )


def test_main_json_and_human_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI output preserves deterministic pass/fail exit semantics."""
    monkeypatch.setattr(
        registry_provenance,
        "validate_repository_registry",
        lambda root: {
            "schema_version": registry_provenance.SCHEMA_VERSION,
            "status": "passed",
            "lock_files": [],
            "violations": [],
        },
    )
    assert registry_provenance.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"

    monkeypatch.setattr(
        registry_provenance,
        "validate_repository_registry",
        lambda root: {
            "schema_version": registry_provenance.SCHEMA_VERSION,
            "status": "failed",
            "lock_files": [],
            "violations": [
                {"code": "registry-hash-mismatch", "path": "lock.txt", "detail": "mismatch"}
            ],
        },
    )
    assert registry_provenance.main([]) == 1
    output = capsys.readouterr().out
    assert "Python lock PyPI provenance: failed" in output
    assert "registry-hash-mismatch: lock.txt: mismatch" in output
