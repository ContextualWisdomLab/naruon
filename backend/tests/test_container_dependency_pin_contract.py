"""Regression contracts for container and release dependency security pins.

The container-provenance process depends on repository tests, not prose alone,
to keep independently versioned Python and JavaScript toolchains on the exact
reviewed security floor.  These checks intentionally read both source manifests
and the generated pnpm lock so a direct pin cannot drift away from the resolved
artifact graph.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_text(relative_path: str) -> str:
    """Return one required repository file as UTF-8 text."""
    path = REPO_ROOT / relative_path
    assert path.is_file(), f"required pin contract file is missing: {relative_path}"
    return path.read_text(encoding="utf-8")


def test_container_provenance_dependency_pins_match_reviewed_manifests() -> None:
    """Keep backend, Strix, and frontend dependency floors reviewable together."""
    backend_requirements = read_repo_text("backend/requirements.txt")
    strix_requirements = read_repo_text("requirements-strix-ci.txt")
    frontend_package = json.loads(read_repo_text("frontend/package.json"))
    frontend_lock = read_repo_text("frontend/pnpm-lock.yaml")

    assert "protobuf==7.35.1" in backend_requirements
    assert "protobuf==6.33.6" in strix_requirements

    assert frontend_package["devDependencies"]["postcss"] == "8.5.24"
    assert frontend_package["devDependencies"]["jsdom"] == "^30.0.1"
    assert frontend_package["overrides"]["brace-expansion"] == "5.0.9"
    assert frontend_package["overrides"]["undici"] == "8.9.0"

    assert "jsdom@30.0.1:" in frontend_lock
    assert "brace-expansion: 5.0.9" in frontend_lock
    assert "undici: 8.9.0" in frontend_lock
