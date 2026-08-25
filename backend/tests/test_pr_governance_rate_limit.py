"""Regression tests for PR-governance semantic review evidence.

These tests exercise the production shell gate with a deterministic fake GitHub CLI.
A successful commit status must not turn an explicitly rate-limited CodeRabbit
review into semantic review evidence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import textwrap


HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
_FAKE_GH_CONFIG_NAME = "fake-gh-config.json"


def _write_fake_gh_config(
    bin_dir: Path, config: dict[str, object] | None = None
) -> None:
    """Write explicit fake-CLI controls without inheriting ambient process state."""

    (bin_dir / _FAKE_GH_CONFIG_NAME).write_text(
        json.dumps(config or {}, separators=(",", ":")),
        encoding="utf-8",
    )


def _write_fake_gh(bin_dir: Path) -> None:
    gh = bin_dir / "gh"
    gh.write_text(
        textwrap.dedent(
            f'''\
            #!/usr/bin/env python3
            import json
            from pathlib import Path
            import sys

            HEAD = "{HEAD_SHA}"
            CONFIG_PATH = Path(sys.argv[0]).with_name("{_FAKE_GH_CONFIG_NAME}")
            CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
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
                emit([{{
                    "name": "Application CI",
                    "state": CONFIG.get("required_check_state", "SUCCESS"),
                    "link": "https://checks/app-ci",
                }}])
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
                    if CONFIG.get("fail_status"):
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
                    if CONFIG.get("fail_check_runs"):
                        print("synthetic check-runs outage", file=sys.stderr)
                        raise SystemExit(1)
                    emit({{"check_runs": []}})
                    raise SystemExit(0)

                if endpoint.endswith("/pulls/42/reviews"):
                    emit([])
                    raise SystemExit(0)

                if endpoint.endswith("/issues/42/comments"):
                    if "--method" in args:
                        emit({{"id": 999}})
                        raise SystemExit(0)
                    if "--jq" in args:
                        raise SystemExit(0)
                    if "--paginate" in args:
                        if CONFIG.get("fail_issue_comments"):
                            print("synthetic issue-comments outage", file=sys.stderr)
                            raise SystemExit(1)
                        # Count raw paginated comment reads so tests can
                        # prove the gate fetches this payload once per run.
                        counter = CONFIG_PATH.with_name("comments-fetch-count")
                        count = int(counter.read_text()) + 1 if counter.exists() else 1
                        counter.write_text(str(count), encoding="utf-8")
                        emit([{{
                            "id": 777,
                            "user": {{"login": "coderabbitai[bot]"}},
                            "created_at": "2026-08-15T00:00:00Z",
                            "body": CONFIG.get(
                                "comment_body",
                                "Review limit reached. We couldn't start this review. "
                                "Next review available later. Head SHA: " + HEAD,
                            ),
                        }}])
                        raise SystemExit(0)
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
    _write_fake_gh_config(bin_dir)


def _gate_environment(bin_dir: Path) -> dict[str, str]:
    """Build the complete deterministic child environment required by the gate."""

    return {
        "PATH": f"{bin_dir}:{os.defpath}",
        "GITHUB_REPOSITORY": "owner/repo",
        "GH_TOKEN": "fake",
        "EVENT_NAME": "pull_request_target",
        "TARGET_PR_NUMBER": "42",
        "DIRECT_PR_NUMBER": "",
        "WORKFLOW_RUN_PR_NUMBER": "",
        "PR_GOVERNANCE_RETRY_SLEEP_SECONDS": "0",
    }


def _run_gate(
    repo_root: Path,
    bin_dir: Path,
    *,
    fake_gh_config: dict[str, object] | None = None,
    gate_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    gate = repo_root / "scripts" / "ci" / "pr_governance_gate.sh"
    _write_fake_gh_config(bin_dir, fake_gh_config)
    env = _gate_environment(bin_dir)
    env.update(gate_env or {})
    return subprocess.run(
        ["bash", str(gate)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_rate_limited_coderabbit_status_requires_structured_fallback(
    tmp_path: Path,
) -> None:
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


def test_review_unavailable_pattern_rejects_unrelated_separator(tmp_path: Path) -> None:
    """Only apostrophe variants may classify a review as not having started."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(
        repo_root,
        bin_dir,
        fake_gh_config={
            "comment_body": (
                "Synthetic unrelated text: we couldnXt start this review. Head SHA: "
                + HEAD_SHA
            )
        },
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Ignoring successful CodeRabbit commit status" not in output
    assert "PR governance metadata gate is ready" in output


def test_malformed_repository_identifier_fails_closed(tmp_path: Path) -> None:
    """Governance API scope must be exactly one owner/repository pair."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(
        repo_root,
        bin_dir,
        gate_env={"GITHUB_REPOSITORY": "owner/repo/extra"},
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "GitHub repository identifier must be owner/repo" in output


def test_repository_identifier_rejects_api_scope_metacharacters(tmp_path: Path) -> None:
    """Repository API scope rejects URL, whitespace, and newline characters."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    for repository in ("owner/repo?x=1", "owner/repo name", "owner/repo\nextra"):
        result = _run_gate(
            repo_root,
            bin_dir,
            gate_env={"GITHUB_REPOSITORY": repository},
        )
        output = result.stdout + result.stderr

        assert result.returncode != 0, (repository, output)
        assert "GitHub repository identifier must be owner/repo" in output


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

    result = _run_gate(
        repo_root,
        bin_dir,
        fake_gh_config={"fail_check_runs": True},
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Current-head check runs could not be read" in output
    assert "PR governance metadata gate errored" not in output


def test_commit_status_lookup_failure_preserves_causal_blocker(tmp_path: Path) -> None:
    """A status API outage must not turn the default empty status into a jq error."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(
        repo_root,
        bin_dir,
        fake_gh_config={"fail_status": True},
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Current-head commit statuses could not be read" in output
    assert "PR governance metadata gate errored" not in output


def test_gate_harness_ignores_ambient_fake_cli_controls(
    tmp_path: Path, monkeypatch
) -> None:
    """Ambient process variables must not alter deterministic fake-CLI behavior."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)
    monkeypatch.setenv(
        "FAKE_GH_COMMENT_BODY",
        "Ambient unrelated text: review available. Head SHA: " + HEAD_SHA,
    )

    result = _run_gate(repo_root, bin_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert (
        "Waiting for current-head CodeRabbit evidence or a structured OpenCode App adversarial approval"
        in output
    )
    assert "PR governance metadata gate is ready" not in output


def test_comments_outage_during_normalization_keeps_status_readable(
    tmp_path: Path,
) -> None:
    """A comments-endpoint hiccup must not corrupt the successful status read."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(
        repo_root,
        bin_dir,
        fake_gh_config={"fail_issue_comments": True},
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert (
        "Current-head commit statuses could not be read" not in output
    ), output
    assert "Review-unavailable comment normalization skipped" in output
    assert "PR issue comments could not be read; see the workflow run log" in output
    assert "PR governance metadata gate errored" not in output


def test_normalization_diagnostic_is_surfaced_on_success_path(tmp_path: Path) -> None:
    """The ignored-status diagnostic must survive the impl's stderr capture."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(repo_root, bin_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Ignoring successful CodeRabbit commit status" in output
    assert "commit status normalization notes:" in output


def test_issue_comments_are_fetched_once_per_gate_run(tmp_path: Path) -> None:
    """Normalization and evaluator evidence must share one comments API call."""

    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_gh(bin_dir)

    result = _run_gate(repo_root, bin_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    counter = bin_dir / "comments-fetch-count"
    assert counter.exists(), output
    assert counter.read_text(encoding="utf-8").strip() == "1", output
    assert "Reusing entrypoint issue-comments snapshot for review evidence." in output


def test_skipped_and_neutral_required_checks_are_accepted(tmp_path: Path) -> None:
    """GitHub's explicit skipped and neutral required states satisfy the gate."""

    repo_root = Path(__file__).resolve().parents[2]

    for state in ("SKIPPED", "NEUTRAL"):
        bin_dir = tmp_path / state.lower()
        bin_dir.mkdir()
        _write_fake_gh(bin_dir)

        result = _run_gate(
            repo_root,
            bin_dir,
            fake_gh_config={"required_check_state": state},
        )
        output = result.stdout + result.stderr

        assert result.returncode == 0, output
        assert (
            f"Required check `Application CI` is {state} on the current head."
            not in output
        )
        assert "PR governance blockers for 42" not in output
        assert (
            "Waiting for current-head CodeRabbit evidence or a structured OpenCode App adversarial approval"
            in output
        )
        assert "PR governance metadata gate is ready" not in output
