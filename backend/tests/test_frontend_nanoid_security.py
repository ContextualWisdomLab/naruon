"""Fail closed when the frontend lock resolves a vulnerable Nano ID release."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_LOCK = REPO_ROOT / "frontend" / "pnpm-lock.yaml"
PATCHED_NANOID_VERSION = "5.1.16"


def test_frontend_lock_resolves_only_patched_nanoid() -> None:
    """Require PostCSS's Nano ID dependency to resolve to the reviewed patched pin."""
    lock = yaml.safe_load(FRONTEND_LOCK.read_text(encoding="utf-8"))

    for section_name in ("packages", "snapshots"):
        section = lock[section_name]
        nanoid_keys = sorted(
            package_key
            for package_key in section
            if package_key.startswith("nanoid@")
        )
        assert nanoid_keys == [f"nanoid@{PATCHED_NANOID_VERSION}"]

    postcss_snapshot = lock["snapshots"]["postcss@8.5.24"]
    assert postcss_snapshot["dependencies"]["nanoid"] == PATCHED_NANOID_VERSION
