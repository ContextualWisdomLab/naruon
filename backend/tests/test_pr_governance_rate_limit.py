"""Regression tests for PR-governance semantic review evidence.

These tests exercise the production shell gate with a deterministic fake GitHub CLI.
A successful commit status must not turn an explicitly rate-limited CodeRabbit
review into semantic review evidence.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write_fake_gh(bin_dir: Path) -> None:
    gh = bin_dir / "gh"
    gh.write_text(
        textwrap.dedent(
            f'''\
            #!/usr/bin/env python3
            import json
            import os
            import sys

            HEAD = "{HEAD_SHA}"
            args = sys.argv[1:]
            joined = " ".join(args)

            def emit(value):
                if isinstance(value, str):
                    print(value, end="")
                else:
                    print(json.dumps(value, separators=(",", ":")), end="")

            if args[:2] == ["pr", "view"]:
                emit({{
                    "number": 42,
                    "state": "OPEN",
                    "headRefOid": HEAD,
                    "isDraft": False,
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "",
                    "statusCheckRollup": [],
                }})
                raise SystemExit(0)

            if args[:2] == ["pr", "checks"]:
                emit([{{"name": "Application CI", "state": "SUCCESS", "link": "https://checks/app-ci"}}])
                raise SystemExit(0)

            if args and args[0] == "api":
                if "graphql" in args:
                    emit({{
                        "data": {{"repository": {{"pullRequest": {{
                            "headRefOid": HEAD,
                            "mergeStateStatus": "CLEAN",
                            "reviewThreads": {{"pageInfo": {{"hasNextPage": False}}, "nodes": []}},
                        }}}}}}
                    }})
                    raise SystemExit(0)

                if "--method" in args:
                    emit({{"id": 999}})
                    raise SystemExit(0)

                endpoint = next((arg for arg in args[1:] if arg.startswith("repos/")), "")

                if endpoint.endswith("/status"):
                    if os.environ.get("FAKE_GH_FAIL_STATUS") == "1":
                        print("synthetic commit-status outage", file=sys.stderr)
                        raise SystemExit(1)
                    emit({{"statuses": [{{
                        "context": "CodeRabbit",
                        "state": "success",
                        "description": "Review completed",
                        "created_at": "2026-08-15T00:00:00Z",
                        "updated_at": "2026-08-15T00:00:00Z",
                    }}]}})
                    raise SystemExit(0)

                if "/check-runs" in endpoint:
                    if os.environ.get("FAKE_GH_FAIL_CHECK_RUNS") == "1":
                        print("synthetic check-runs outage", file=sys.stderr)
                        raise SystemExit(1)
                    emit({{"check_runs": []}})
                    raise SystemExit(0)

                if endpoint.endswith("/pulls/42/reviews"):
                    emit([])
                    raise SystemExit(0)

                if endpoint.endswith("/issues/42/comments"):
                    if "--jq" in args:
                        raise SystemExit(0)
                    emit([{{
                        "id": 777,
                        "user": {{"login": "coderabbitai[bot]"}},
                        "created_at": "2026-08-15T00:00:00Z",
                        "body": (
                            "Review limit reached. We couldn't start this review. "
                            "Next review available later. Head SHA: " + HEAD
                        ),
                    }}])
                    raise SystemExit(0)

                if endpoint.endswith("/pulls/42/comments"):
                    emit([])
                    raise SystemExit(0)

                if endpoint.endswith("/pulls/42"):
                    emit({{"state": "open", "head": {{"sha": HEAD}}}})
                    raise SystemExit(0)

            print("unexpected gh invocation: " + joined, file=sys.stderr)
            raise SystemExit(99)
            '''
        ),
        encoding="utf-8",
    )
    gh.chmod(0o755)


def _gate_environment(bin_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "GITHUB_REPOSITORY": "owner/repo",
            "GH_TOKEN": "fake",
            "EVENT_NAME": "pull_request_target",
            "TARGET_PR_NUMBER": "42",
            "DIRECT_PR_NUMBER": "",
            "WORKFLOW_RUN_PR_NUMBER": "",
            "PR_GOVERNANCE_RETRY_SLEEP_SECONDS": "0",
        }
    )
    # The production implementation hardens PATH when GITHUB_ACTIONS is set,
    # which would intentionally hide this test's deterministic fake `gh`.
    env.pop("GITHUB_ACTIONS", None)
    return env


def _run_gate(repo_root: Path, bin_dir: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
    gate = repo_root / "scripts" / "ci" / "pr_governance_gate.sh"
    env = _gate_environment(bin_dir)
    env.update(extra_env)
    return subprocess.run(
        ["bash", str(gate)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_rate_limited_coderabbit_status_requires_structured_fallback(tmp_path: Path) -> None:
    """A status-only success cannot certify a CodeRabbit review that never ran."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(repo_root, bin_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert (
        "Waiting for current-head CodeRabbit evidence or a structured OpenCode App adversarial approval"
        in output
    )
    assert "PR governance metadata gate is ready" not in output


def test_actions_entrypoint_hardens_path_before_resolving_gh() -> None:
    """Actions must resolve the trusted GitHub CLI only after PATH hardening."""

    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "scripts" / "ci" / "pr_governance_gate.sh").read_text(
        encoding="utf-8"
    )
    hardening = 'if [ -n "${GITHUB_ACTIONS:-}" ]; then'
    resolution = 'PR_GOVERNANCE_REAL_GH="$(command -v gh || true)"'

    assert hardening in source
    assert source.index(hardening) < source.index(resolution)


def test_check_run_lookup_failure_is_an_explicit_blocker(tmp_path: Path) -> None:
    """A check-runs API outage must fail closed with a causal blocker."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(repo_root, bin_dir, FAKE_GH_FAIL_CHECK_RUNS="1")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Current-head check runs could not be read" in output
    assert "PR governance metadata gate errored" not in output
