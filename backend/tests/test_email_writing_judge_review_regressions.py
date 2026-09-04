"""Regressions for current-head Task 7 review findings."""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

import services.email_writing_judge as judge_module
from services.email_writing_judge import (
    EmailWritingIndependentJudge,
    EmailWritingJudgeError,
    _invoke_judge_runner,
    export_judge_response_matrix,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_GUARD = _REPOSITORY_ROOT / "scripts" / "ci" / "reject_terminal_output.sh"
_TASK7_WORKFLOW = _REPOSITORY_ROOT / ".github" / "workflows" / "email-writing-judge-tdd.yml"


class _UnserializableMappingRunner:
    """Return a mapping that strict Judge JSON cannot serialize."""

    def judge(self, **_kwargs: object) -> object:
        """Return one deliberately non-JSON-safe Judge-shaped mapping."""
        return {"criterion_categories": {"issue_support": object()}}


class _BlockingRunner:
    """Expose the worker-thread daemon contract while simulating a hung provider."""

    def __init__(self, release: threading.Event) -> None:
        """Keep the release event used to let the test worker terminate cleanly."""
        self.release = release
        self.worker_daemon: bool | None = None
        self.started = threading.Event()

    def judge(self, **_kwargs: object) -> object:
        """Record worker daemon state and block until the test releases the call."""
        self.worker_daemon = threading.current_thread().daemon
        self.started.set()
        self.release.wait(timeout=2.0)
        return {}


def test_mapping_serialization_failure_is_redacted_to_stable_judge_error() -> None:
    """A non-JSON runner mapping must never leak a raw TypeError."""
    judge = EmailWritingIndependentJudge(_UnserializableMappingRunner())

    class _Candidate:
        suggested_replacement = "확인 부탁드립니다."

        def model_dump(self) -> dict[str, object]:
            return {
                "category_code": "clarity",
                "priority": "important",
                "title": "확인 요청",
                "explanation": "범위를 확인합니다.",
                "suggested_replacement": self.suggested_replacement,
                "candidate_evidence_ids": ["draft"],
                "selector": {"type": "TextPositionSelector", "start": 0, "end": 2},
            }

    class _Context:
        current_draft = "확인"
        subject = "범위"

        def to_prompt_payload(self) -> dict[str, object]:
            return {"subject": self.subject, "current_draft": self.current_draft}

    with pytest.raises(EmailWritingJudgeError) as captured:
        judge.evaluate(
            _Candidate(),
            _Context(),
            candidate_model_profile_id="candidate-profile",
            judge_model_profile_id="judge-profile",
        )

    assert captured.value.code == "judge_payload_invalid"
    assert type(captured.value) is EmailWritingJudgeError


def test_unavailable_matrix_package_is_dependency_injected() -> None:
    """Package-unavailable coverage must not depend on the test environment."""

    def _missing_symbols() -> object:
        raise EmailWritingJudgeError("judge_package_unavailable")

    with pytest.raises(EmailWritingJudgeError) as captured:
        export_judge_response_matrix(
            ((0,),),
            n_categories=4,
            symbol_loader=_missing_symbols,
        )

    assert captured.value.code == "judge_matrix_validator_unavailable"


def test_timed_out_judge_runner_uses_a_daemon_worker() -> None:
    """A provider call that outlives its deadline must not hold process exit open."""
    release = threading.Event()
    runner = _BlockingRunner(release)
    try:
        with pytest.raises(EmailWritingJudgeError) as captured:
            _invoke_judge_runner(
                runner,
                deadline_seconds=0.01,
                task="task",
                answer="answer",
                criteria=[],
                reference_answer="reference",
                category_count=4,
            )
        assert captured.value.code == "judge_runner_failed"
        assert runner.started.is_set()
        assert runner.worker_daemon is True
    finally:
        release.set()


def test_task7_workflow_does_not_bootstrap_background_workers_from_environment() -> None:
    """Focused Judge tests must not import the application solely to disable workers."""
    workflow = _TASK7_WORKFLOW.read_text(encoding="utf-8")

    assert "DISABLE_BACKGROUND_WORKERS" not in workflow
    assert workflow.count("--noconftest") >= 2


def test_terminal_output_guard_preserves_success_and_rejects_policy_tokens() -> None:
    """The workflow wrapper must fail even when a command prints a forbidden token."""
    clean = subprocess.run(
        ["bash", str(_OUTPUT_GUARD), sys.executable, "-c", "print('clean')"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert clean.returncode == 0
    assert clean.stdout.strip() == "clean"

    forbidden = subprocess.run(
        ["bash", str(_OUTPUT_GUARD), sys.executable, "-c", "print('Denied')"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert forbidden.returncode != 0
    assert "Denied" in forbidden.stdout


def test_terminal_output_guard_preserves_command_failure_status() -> None:
    """The wrapper must not convert an ordinary command failure into success."""
    failed = subprocess.run(
        ["bash", str(_OUTPUT_GUARD), sys.executable, "-c", "raise SystemExit(23)"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 23


def test_daemon_judge_executor_skips_cancelled_queued_work() -> None:
    """Cancelled queued work must not invoke its provider callback."""
    executor = judge_module._DaemonJudgeRunnerExecutor()
    started = threading.Event()
    release = threading.Event()
    cancelled_call_ran = threading.Event()

    def block_worker() -> None:
        started.set()
        release.wait(timeout=2.0)

    first = executor.submit(block_worker)
    assert started.wait(timeout=1.0)
    cancelled = executor.submit(cancelled_call_ran.set)
    assert cancelled.cancel()
    release.set()
    first.result(timeout=1.0)
    executor.submit(lambda: None).result(timeout=1.0)

    assert not cancelled_call_ran.is_set()


def test_judge_executor_lock_reuses_instance_created_by_another_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inner lock check must preserve an executor installed concurrently."""
    installed = judge_module._DaemonJudgeRunnerExecutor()

    class InstallingLock:
        def __enter__(self) -> None:
            judge_module._JUDGE_RUNNER_EXECUTOR = installed

        def __exit__(self, *args: object) -> None:
            del args

    monkeypatch.setattr(judge_module, "_JUDGE_RUNNER_EXECUTOR", None)
    monkeypatch.setattr(judge_module, "_JUDGE_RUNNER_EXECUTOR_LOCK", InstallingLock())

    assert judge_module._get_judge_runner_executor() is installed
