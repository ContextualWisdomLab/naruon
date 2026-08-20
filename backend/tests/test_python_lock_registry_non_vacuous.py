"""Non-vacuous evidence contracts for PyPI lock provenance."""

from __future__ import annotations

import importlib.util
import json
import runpy
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "python_lock_registry_provenance.py"
_spec = importlib.util.spec_from_file_location("python_lock_registry_non_vacuous", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
registry_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = registry_provenance
_spec.loader.exec_module(registry_provenance)


def _sha() -> str:
    """Return one deterministic SHA-256 fixture digest."""
    return "a" * 64


def _codes(receipt: dict[str, object]) -> set[str]:
    """Return stable top-level violation codes from a repository receipt."""
    return {str(item["code"]) for item in receipt["violations"]}


def test_repository_without_hash_locks_fails_non_vacuously(tmp_path: Path) -> None:
    """A green registry receipt must represent at least one discovered hash lock."""
    (tmp_path / "requirements.txt").write_text("example==1.0\n", encoding="utf-8")

    receipt = registry_provenance.validate_repository_registry(
        tmp_path,
        fetch_release=lambda project, version: {},
    )

    assert receipt["status"] == "failed"
    assert receipt["lock_files"] == []
    assert _codes(receipt) == {"registry-no-hash-locks"}


class _Response:
    """Minimal exact-origin PyPI response used by the script-entrypoint test."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        self.payload = json.dumps(
            {
                "info": {"name": "example", "version": "1.0"},
                "urls": [
                    {
                        "packagetype": "sdist",
                        "yanked": False,
                        "digests": {"sha256": _sha()},
                    }
                ],
            }
        ).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def geturl(self) -> str:
        """Return the unchanged trusted request URL."""
        return self.url

    def read(self, size: int) -> bytes:
        """Return a bounded response body."""
        return self.payload[:size]


def test_script_main_guard_runs_registry_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Executing the script as __main__ publishes a passing JSON receipt and exits zero."""
    lock = tmp_path / "requirements-hashes.txt"
    lock.write_text(
        f"example==1.0 \\\n    --hash=sha256:{_sha()}\n",
        encoding="utf-8",
    )

    class _Opener:
        def open(self, request: urllib.request.Request, timeout: float) -> _Response:
            return _Response(request.full_url)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _Opener())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--repository-root",
            str(tmp_path),
            "--json",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
