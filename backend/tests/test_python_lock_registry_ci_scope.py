"""Regression contracts for PyPI registry-provenance CI scoping."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_CI = REPOSITORY_ROOT / ".github" / "workflows" / "app-ci.yml"


def _application_ci_text() -> str:
    """Read the repository-owned Application CI workflow as UTF-8 text."""
    return APPLICATION_CI.read_text(encoding="utf-8")


def test_registry_provenance_is_scoped_after_offline_validation() -> None:
    """Keep live-PyPI evidence off unrelated PRs without weakening lock validation."""
    workflow = _application_ci_text()

    offline_index = workflow.index("- name: Validate Python lock provenance")
    scope_index = workflow.index(
        "- name: Determine whether PyPI registry provenance is required"
    )
    registry_index = workflow.index("- name: Validate PyPI release hash provenance")
    install_index = workflow.index("- name: Install backend dependencies")

    assert offline_index < scope_index < registry_index < install_index
    assert "id: registry_scope" in workflow[scope_index:registry_index]
    assert 'git diff --name-only "$BASE_SHA" HEAD' in workflow[scope_index:registry_index]
    assert "requirements[^/]*\\.txt" in workflow[scope_index:registry_index]
    assert 'echo "required=$required" >> "$GITHUB_OUTPUT"' in workflow[
        scope_index:registry_index
    ]

    registry_block = workflow[registry_index:install_index]
    assert "if: steps.registry_scope.outputs.required == 'true'" in registry_block


def test_registry_scope_fails_safe_when_base_cannot_be_compared() -> None:
    """Unknown comparison state must require the network provenance gate."""
    workflow = _application_ci_text()
    scope_index = workflow.index(
        "- name: Determine whether PyPI registry provenance is required"
    )
    registry_index = workflow.index("- name: Validate PyPI release hash provenance")
    scope_block = workflow[scope_index:registry_index]

    assert "required=true" in scope_block
    base_sha_expression = (
        'BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}'
    )
    assert base_sha_expression in scope_block
    assert '"0000000000000000000000000000000000000000"' in scope_block
