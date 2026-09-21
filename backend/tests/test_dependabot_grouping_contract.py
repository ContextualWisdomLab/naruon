"""Keep automated dependency PRs inside a reviewable compatibility boundary."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPENDABOT_CONFIG = REPO_ROOT / ".github" / "dependabot.yml"


def _update_config(package_ecosystem: str, directory: str) -> dict[str, object]:
    """Return one Dependabot update stanza identified by ecosystem and directory."""
    config = yaml.safe_load(DEPENDABOT_CONFIG.read_text(encoding="utf-8"))
    matches = [
        update
        for update in config["updates"]
        if update["package-ecosystem"] == package_ecosystem
        and update["directory"] == directory
    ]
    assert len(matches) == 1
    return matches[0]


def _group(update: dict[str, object], group_name: str) -> dict[str, object]:
    """Return one required group from an update stanza."""
    groups = update["groups"]
    assert isinstance(groups, dict)
    group = groups[group_name]
    assert isinstance(group, dict)
    return group


def test_bulk_version_groups_bundle_patch_updates_only() -> None:
    """Keep high-change minor and major releases out of wildcard mega-PRs."""
    group_specs = (
        ("pip", "/backend", "backend-python"),
        ("pip", "/", "ci-python"),
        ("npm", "/frontend", "frontend-npm"),
    )

    for ecosystem, directory, group_name in group_specs:
        group = _group(_update_config(ecosystem, directory), group_name)
        assert group["applies-to"] == "version-updates"
        assert group["update-types"] == ["patch"]


def test_root_ci_pip_scan_does_not_cross_owned_runtime_trees() -> None:
    """Keep root CI updates from recursively absorbing backend and connector manifests."""
    root_pip = _update_config("pip", "/")
    excluded_paths = root_pip["exclude-paths"]
    assert isinstance(excluded_paths, list)
    assert "backend/**" in excluded_paths
    assert "connector/**" in excluded_paths


def test_backend_security_material_patch_is_not_hidden_in_bulk_group() -> None:
    """Keep the current SMTP command-injection hardening update independently reviewable."""
    group = _group(_update_config("pip", "/backend"), "backend-python")
    assert "aiosmtplib" in group["exclude-patterns"]