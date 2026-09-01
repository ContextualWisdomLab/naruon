"""Regression contract for Application CI hosted-runner acquisition.

The organization has observed current-head jobs remain queued before checkout when
repository workflows use the floating ``ubuntu-latest`` selector.  Naruon's
Application CI therefore names an explicit supported GitHub-hosted image so a
future label drift cannot silently restore the same pre-checkout starvation class.
"""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_CI_PATH = REPO_ROOT / ".github" / "workflows" / "app-ci.yml"
EXPECTED_HOSTED_RUNNER = "ubuntu-24.04"


def test_application_ci_jobs_use_explicit_supported_hosted_runner() -> None:
    """Keep both product CI lanes on the explicit hosted image proven to acquire."""
    workflow = yaml.safe_load(APPLICATION_CI_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    assert jobs["backend"]["runs-on"] == EXPECTED_HOSTED_RUNNER
    assert jobs["frontend"]["runs-on"] == EXPECTED_HOSTED_RUNNER
