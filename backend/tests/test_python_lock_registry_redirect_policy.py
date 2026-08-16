"""Redirect-origin contract for the PyPI lock-provenance transport."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "python_lock_registry_provenance.py"
_spec = importlib.util.spec_from_file_location("python_lock_registry_redirect", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
registry_provenance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = registry_provenance
_spec.loader.exec_module(registry_provenance)


class _RedirectedResponse:
    """Minimal urllib response exposing the final URL after redirect handling."""

    def __init__(self, final_url: str) -> None:
        self._final_url = final_url
        self.headers = {"Content-Type": "application/json"}
        self._payload = json.dumps(
            {
                "info": {"name": "example", "version": "1.0"},
                "urls": [],
            }
        ).encode("utf-8")

    def __enter__(self) -> "_RedirectedResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def geturl(self) -> str:
        """Return the final response URL observed by urllib."""
        return self._final_url

    def read(self, size: int) -> bytes:
        """Return a bounded JSON payload."""
        return self._payload[:size]


def test_fetch_rejects_redirect_to_non_pypi_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTPS redirect must not move trusted metadata reads off pypi.org."""
    monkeypatch.setattr(
        registry_provenance.urllib.request,
        "urlopen",
        lambda request, timeout: _RedirectedResponse(
            "https://metadata.attacker.invalid/pypi/example/1.0/json"
        ),
    )

    with pytest.raises(ValueError, match="trusted PyPI origin"):
        registry_provenance.fetch_pypi_release("example", "1.0")


def test_fetch_accepts_final_exact_pypi_release_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response that remains on the exact requested PyPI URL is accepted."""
    expected_url = registry_provenance.build_pypi_release_url("example", "1.0")
    monkeypatch.setattr(
        registry_provenance.urllib.request,
        "urlopen",
        lambda request, timeout: _RedirectedResponse(expected_url),
    )

    metadata = registry_provenance.fetch_pypi_release("example", "1.0")

    assert metadata["info"] == {"name": "example", "version": "1.0"}
