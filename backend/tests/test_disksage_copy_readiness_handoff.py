import hashlib
import inspect
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
import time

import pytest

from scripts import disksage_copy_readiness_handoff as handoff


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "disksage_copy_readiness_handoff.py"
)


def _success_payload() -> dict[str, object]:
    return {
        "ok": True,
        "schema_kind": "disksage.naruon.cloud-copy-readiness",
        "schema_version": 3,
        "provider": "icloud",
        "readiness_state": "blocked",
        "candidate_count": 19,
        "candidate_bytes": 3_575_671_927,
        "readiness_fingerprint_sha256": "8e6e5592fe4ab53ed60bf17d017e3c8e6c959416638d6ae72698acda82990070",
        "local_paths_included": False,
        "relative_names_included": False,
        "raw_metadata_values_included": False,
        "cloud_write_executed": False,
        "source_eviction_authorized": False,
    }


def _python_verifier(path: Path, source: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{source}", encoding="utf-8")
    path.chmod(0o700)
    return path


def _json_verifier(path: Path, payload: dict[str, object], exit_code: int) -> Path:
    return _python_verifier(
        path,
        "import json\n"
        f"print(json.dumps({payload!r}, sort_keys=True))\n"
        f"raise SystemExit({exit_code})\n",
    )


def _raw_json_verifier(path: Path, raw_json: str, exit_code: int) -> Path:
    return _python_verifier(
        path,
        f"import sys\nsys.stdout.write({raw_json!r})\nraise SystemExit({exit_code})\n",
    )


def _verifier_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _handoff_args(
    verifier: Path | str, readiness: Path | str, *, expected_sha256: str | None = None
) -> list[str]:
    verifier_path = Path(verifier)
    if expected_sha256 is None:
        expected_sha256 = _verifier_sha256(verifier_path)
    return [
        "--verifier",
        str(verifier),
        "--verifier-sha256",
        expected_sha256,
        str(readiness),
    ]


def test_module_level_runtime_surface_has_docstrings():
    undocumented = sorted(
        name
        for name, value in vars(handoff).items()
        if getattr(value, "__module__", None) == handoff.__name__
        and (inspect.isfunction(value) or inspect.isclass(value))
        and not (isinstance(value.__doc__, str) and value.__doc__.strip())
    )

    assert undocumented == []


def test_main_delegates_to_absolute_verifier_without_shell_env_or_input_read(
    tmp_path, monkeypatch, capsys
):
    verifier = _python_verifier(
        tmp_path / "verifier ; touch must-not-exist",
        "import json, os, sys\n"
        "assert os.getcwd() == '/'\n"
        "assert 'NARUON_HANDOFF_SECRET' not in os.environ\n"
        "assert sys.stdin.read() == ''\n"
        f"print(json.dumps({_success_payload()!r}, sort_keys=True))\n",
    )
    readiness = tmp_path / "does not need to exist.json"
    monkeypatch.setenv("NARUON_HANDOFF_SECRET", "must-not-reach-child")

    assert handoff.main(_handoff_args(verifier, readiness)) == 0
    assert json.loads(capsys.readouterr().out) == _success_payload()
    assert not (tmp_path / "must-not-exist").exists()


def test_main_accepts_current_disksage_schema_version_four(tmp_path, capsys):
    payload = _success_payload()
    payload["schema_version"] = 4
    verifier = _json_verifier(tmp_path / "verifier", payload, 0)

    assert handoff.main(_handoff_args(verifier, tmp_path / "readiness.json")) == 0
    assert json.loads(capsys.readouterr().out) == payload


@pytest.mark.parametrize("exit_code", [64, 65])
def test_main_preserves_valid_disksage_failure_protocol(tmp_path, capsys, exit_code):
    payload = {
        "ok": False,
        "error_code": "naruon-copy-readiness-fingerprint-invalid",
    }
    verifier = _json_verifier(tmp_path / "verifier", payload, exit_code)
    readiness = tmp_path / "readiness.json"

    assert handoff.main(_handoff_args(verifier, readiness)) == exit_code
    assert json.loads(capsys.readouterr().out) == payload


def test_main_accepts_bounded_redacted_usage_stderr_from_rust_contract(
    tmp_path, capsys
):
    payload = {
        "ok": False,
        "error_code": "naruon-copy-readiness-verifier-usage-invalid",
    }
    verifier = _python_verifier(
        tmp_path / "verifier",
        "import json, sys\n"
        f"print(json.dumps({payload!r}, sort_keys=True))\n"
        "print('sensitive usage detail', file=sys.stderr)\n"
        "raise SystemExit(64)\n",
    )
    readiness = tmp_path / "readiness.json"

    assert handoff.main(_handoff_args(verifier, readiness)) == 64
    captured = capsys.readouterr()
    assert json.loads(captured.out) == payload
    assert captured.err == ""
    assert "sensitive usage detail" not in captured.out


def test_main_rejects_duplicate_json_object_names_without_leakage(tmp_path, capsys):
    success_json = json.dumps(_success_payload(), sort_keys=True)
    ambiguous_success = success_json.replace(
        '"provider": "icloud"',
        '"provider": "sensitive-private-value", "provider": "icloud"',
    )
    ambiguous_failure = (
        '{"ok":false,"error_code":"sensitive-private-value",'
        '"error_code":"naruon-copy-readiness-fingerprint-invalid"}'
    )

    for index, (raw_json, exit_code) in enumerate(
        ((ambiguous_success, 0), (ambiguous_failure, 65))
    ):
        verifier = _raw_json_verifier(
            tmp_path / f"verifier-{index}", raw_json, exit_code
        )
        readiness = tmp_path / f"readiness-{index}.json"

        assert handoff.main(_handoff_args(verifier, readiness)) == 70
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {
            "ok": False,
            "error_code": "disksage-verifier-protocol-invalid",
        }
        assert captured.err == ""
        assert "sensitive-private-value" not in captured.out


def test_main_rejects_relative_or_untrusted_paths(tmp_path, capsys):
    readiness = tmp_path / "readiness.json"
    target = _json_verifier(tmp_path / "target", _success_payload(), 0)
    non_executable = tmp_path / "non-executable"
    non_executable.write_text("not executable", encoding="utf-8")
    directory = tmp_path / "directory"
    directory.mkdir()
    symlink = tmp_path / "verifier-link"
    symlink.symlink_to(target)

    assert (
        handoff.main(_handoff_args("relative", readiness, expected_sha256="0" * 64))
        == 66
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-unavailable",
    }
    assert handoff.main(_handoff_args(symlink, readiness)) == 66
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-unavailable",
    }
    for invalid_verifier in (non_executable, directory):
        assert (
            handoff.main(
                _handoff_args(invalid_verifier, readiness, expected_sha256="0" * 64)
            )
            == 66
        )
        assert json.loads(capsys.readouterr().out) == {
            "ok": False,
            "error_code": "disksage-verifier-unavailable",
        }
    assert handoff.main(_handoff_args(target, "private.json")) == 64
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "naruon-copy-readiness-input-path-not-absolute",
    }


def test_main_requires_valid_verifier_digest(tmp_path, capsys):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    readiness = tmp_path / "readiness.json"

    assert handoff.main(["--verifier", str(verifier), str(readiness)]) == 64
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-handoff-usage-invalid",
    }
    assert (
        handoff.main(_handoff_args(verifier, readiness, expected_sha256="NOT-A-SHA256"))
        == 64
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-sha256-invalid",
    }


def test_main_rejects_verifier_provenance_mismatch_without_execution(tmp_path, capsys):
    executed = tmp_path / "executed"
    verifier = _python_verifier(
        tmp_path / "verifier",
        f"from pathlib import Path\nPath({str(executed)!r}).touch()\n",
    )
    readiness = tmp_path / "readiness.json"

    assert (
        handoff.main(_handoff_args(verifier, readiness, expected_sha256="0" * 64)) == 66
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-provenance-mismatch",
    }
    assert not executed.exists()


def test_main_executes_digest_bound_private_snapshot(tmp_path, monkeypatch, capsys):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    original_bytes = verifier.read_bytes()
    readiness = tmp_path / "readiness.json"

    def fake_run(snapshot: Path, received_readiness: Path) -> handoff.VerifierResult:
        assert snapshot != verifier
        assert snapshot.parent != verifier.parent
        assert snapshot.read_bytes() == original_bytes
        assert received_readiness == readiness
        verifier.write_bytes(b"tampered after provenance verification")
        assert snapshot.read_bytes() == original_bytes
        return handoff.VerifierResult(0, json.dumps(_success_payload()).encode(), b"")

    monkeypatch.setattr(handoff, "_run_bounded_verifier", fake_run)

    assert handoff.main(_handoff_args(verifier, readiness)) == 0
    assert json.loads(capsys.readouterr().out) == _success_payload()


def test_main_normalizes_snapshot_creation_failure_without_leakage(
    tmp_path, monkeypatch, capsys
):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    readiness = tmp_path / "readiness.json"
    args = _handoff_args(verifier, readiness)

    def fail_temporary_directory(*_args, **_kwargs):
        raise OSError("private temp path must not leak")

    monkeypatch.setattr(
        handoff.tempfile, "TemporaryDirectory", fail_temporary_directory
    )

    assert handoff.main(args) == 70
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "ok": False,
        "error_code": "disksage-verifier-snapshot-failed",
    }
    assert captured.err == ""
    assert "private temp path" not in captured.out


def test_main_normalizes_snapshot_cleanup_failure_without_leakage(
    tmp_path, monkeypatch, capsys
):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    readiness = tmp_path / "readiness.json"
    args = _handoff_args(verifier, readiness)
    original_temporary_directory = handoff.tempfile.TemporaryDirectory

    class CleanupFailure:
        def __init__(self, *temp_args, **temp_kwargs):
            self.delegate = original_temporary_directory(*temp_args, **temp_kwargs)
            self.name = self.delegate.name

        def cleanup(self):
            self.delegate.cleanup()
            raise OSError("private cleanup path must not leak")

    monkeypatch.setattr(handoff.tempfile, "TemporaryDirectory", CleanupFailure)

    assert handoff.main(args) == 70
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "ok": False,
        "error_code": "disksage-verifier-snapshot-failed",
    }
    assert captured.err == ""
    assert "private cleanup path" not in captured.out


def test_main_rejects_short_snapshot_write_without_execution(
    tmp_path, monkeypatch, capsys
):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    readiness = tmp_path / "readiness.json"
    args = _handoff_args(verifier, readiness)
    original_open = Path.open

    class ShortWriter:
        def __init__(self, destination):
            self.destination = destination
            self.first_write = True

        def __enter__(self):
            self.destination.__enter__()
            return self

        def __exit__(self, *exc_info):
            return self.destination.__exit__(*exc_info)

        def fileno(self):
            return self.destination.fileno()

        def write(self, data):
            if self.first_write:
                self.first_write = False
                return self.destination.write(data[:1])
            return 0

    def short_snapshot_open(path, *open_args, **open_kwargs):
        destination = original_open(path, *open_args, **open_kwargs)
        if path.parent.name.startswith("naruon-disksage-verifier-"):
            return ShortWriter(destination)
        return destination

    monkeypatch.setattr(Path, "open", short_snapshot_open)

    def must_not_execute(*_args, **_kwargs):
        pytest.fail("a short verifier snapshot was executed")

    monkeypatch.setattr(handoff, "_run_bounded_verifier", must_not_execute)

    assert handoff.main(args) == 70
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-snapshot-failed",
    }


def test_main_completes_repeated_short_snapshot_writes(tmp_path, monkeypatch, capsys):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    readiness = tmp_path / "readiness.json"
    original_open = Path.open

    class OneByteWriter:
        def __init__(self, destination):
            self.destination = destination

        def __enter__(self):
            self.destination.__enter__()
            return self

        def __exit__(self, *exc_info):
            return self.destination.__exit__(*exc_info)

        def fileno(self):
            return self.destination.fileno()

        def write(self, data):
            return self.destination.write(data[:1])

    def one_byte_snapshot_open(path, *open_args, **open_kwargs):
        destination = original_open(path, *open_args, **open_kwargs)
        if path.parent.name.startswith("naruon-disksage-verifier-"):
            return OneByteWriter(destination)
        return destination

    monkeypatch.setattr(Path, "open", one_byte_snapshot_open)

    assert handoff.main(_handoff_args(verifier, readiness)) == 0
    assert json.loads(capsys.readouterr().out) == _success_payload()


@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
def test_main_rejects_path_replacement_after_precheck(
    tmp_path, monkeypatch, capsys, replacement
):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    replacement_target = _json_verifier(
        tmp_path / "replacement-target", _success_payload(), 0
    )
    readiness = tmp_path / "readiness.json"
    args = _handoff_args(verifier, readiness)
    original_check = handoff._verifier_is_executable_regular_file

    def approve_then_replace(path: Path) -> bool:
        assert original_check(path)
        path.unlink()
        if replacement == "symlink":
            path.symlink_to(replacement_target)
        else:
            os.mkfifo(path, mode=0o700)
        return True

    monkeypatch.setattr(
        handoff, "_verifier_is_executable_regular_file", approve_then_replace
    )

    assert handoff.main(args) == 66
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-unavailable",
    }


def test_verifier_preflight_handles_lstat_failure(tmp_path):
    assert not handoff._verifier_is_executable_regular_file(tmp_path / "missing")


def test_snapshot_rejects_growth_beyond_bound_and_swallows_close_failure(
    tmp_path, monkeypatch
):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    expected_sha256 = _verifier_sha256(verifier)
    original_fstat = handoff.os.fstat
    source_stat_hidden = False

    def hide_source_size(file_descriptor):
        nonlocal source_stat_hidden
        metadata = original_fstat(file_descriptor)
        if source_stat_hidden:
            return metadata
        source_stat_hidden = True
        values = list(metadata)
        values[6] = 0
        return os.stat_result(values)

    monkeypatch.setattr(handoff.os, "fstat", hide_source_size)
    monkeypatch.setattr(handoff, "MAX_VERIFIER_BYTES", 1)

    with pytest.raises(handoff.HandoffError) as error:
        with handoff._verified_verifier_snapshot(verifier, expected_sha256):
            pytest.fail("an oversized growing verifier snapshot was yielded")

    assert error.value.error_code == "disksage-verifier-unavailable"

    monkeypatch.setattr(handoff, "MAX_VERIFIER_BYTES", 256 * 1024 * 1024)
    monkeypatch.setattr(handoff.os, "fstat", original_fstat)
    original_open = handoff.os.open
    original_close = handoff.os.close
    source_file_descriptor = None

    def record_source_open(path, flags, *args, **kwargs):
        nonlocal source_file_descriptor
        file_descriptor = original_open(path, flags, *args, **kwargs)
        if Path(path) == verifier:
            source_file_descriptor = file_descriptor
        return file_descriptor

    def close_then_fail(file_descriptor):
        original_close(file_descriptor)
        if file_descriptor == source_file_descriptor:
            raise OSError("close failure must be ignored")

    monkeypatch.setattr(handoff.os, "open", record_source_open)
    monkeypatch.setattr(handoff.os, "close", close_then_fail)
    with handoff._verified_verifier_snapshot(verifier, expected_sha256) as snapshot:
        assert snapshot.read_bytes() == verifier.read_bytes()


class _TerminationProcess:
    def __init__(self, *, polls=(), waits=(), kill_error=False):
        self.pid = 4242
        self._polls = list(polls)
        self._waits = list(waits)
        self.kill_error = kill_error
        self.kill_count = 0

    def poll(self):
        return self._polls.pop(0)

    def kill(self):
        self.kill_count += 1
        if self.kill_error:
            raise OSError("kill failed")

    def wait(self, timeout):
        outcome = self._waits.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_terminate_process_group_covers_platform_and_reap_failures(monkeypatch):
    monkeypatch.setattr(handoff.os, "name", "nt")
    kill_failure = _TerminationProcess(polls=[None], waits=[0], kill_error=True)
    handoff._terminate_process_group(kill_failure)
    assert kill_failure.kill_count == 1

    already_exited = _TerminationProcess(polls=[0], waits=[0])
    handoff._terminate_process_group(already_exited)
    assert already_exited.kill_count == 0

    monkeypatch.setattr(handoff.os, "name", "posix")
    monkeypatch.setattr(handoff.os, "killpg", lambda *_args: None)
    timeout = subprocess.TimeoutExpired("verifier", 1)
    repeated_timeout = _TerminationProcess(
        polls=[None], waits=[timeout, timeout], kill_error=True
    )
    handoff._terminate_process_group(repeated_timeout)
    assert repeated_timeout.kill_count == 1

    completed_during_timeout = _TerminationProcess(polls=[0], waits=[timeout, 0])
    handoff._terminate_process_group(completed_during_timeout)
    assert completed_during_timeout.kill_count == 0

    wait_failure = _TerminationProcess(waits=[OSError("wait failed")])
    handoff._terminate_process_group(wait_failure)


def test_run_bounded_verifier_normalizes_spawn_and_selector_failures(
    tmp_path, monkeypatch
):
    original_popen = subprocess.Popen

    def spawn_failure(*_args, **_kwargs):
        raise OSError("private executable path")

    monkeypatch.setattr(handoff.subprocess, "Popen", spawn_failure)
    with pytest.raises(handoff.HandoffError) as error:
        handoff._run_bounded_verifier(Path("/verifier"), Path("/readiness"))
    assert error.value.error_code == "disksage-verifier-exec-failed"

    verifier = _python_verifier(tmp_path / "verifier", "import time\ntime.sleep(30)\n")
    monkeypatch.setattr(handoff.subprocess, "Popen", original_popen)

    class RegisterFailureSelector:
        def register(self, *_args, **_kwargs):
            raise OSError("selector registration failed")

        def close(self):
            return None

    monkeypatch.setattr(handoff.selectors, "DefaultSelector", RegisterFailureSelector)
    with pytest.raises(handoff.HandoffError) as error:
        handoff._run_bounded_verifier(verifier, tmp_path / "readiness.json")
    assert error.value.error_code == "disksage-verifier-exec-failed"


@pytest.mark.parametrize("missing_pipe", ["stdout", "stderr"])
def test_run_bounded_verifier_fails_closed_when_spawn_omits_pipe(
    monkeypatch, missing_pipe
):
    class MissingPipeProcess:
        pid = 4242
        stdout = None if missing_pipe == "stdout" else object()
        stderr = None if missing_pipe == "stderr" else object()

    process = MissingPipeProcess()
    terminated = []
    monkeypatch.setattr(handoff.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(
        handoff,
        "_terminate_process_group",
        lambda candidate: terminated.append(candidate),
    )

    with pytest.raises(handoff.HandoffError) as error:
        handoff._run_bounded_verifier(Path("/verifier"), Path("/readiness"))

    assert error.value.error_code == "disksage-verifier-exec-failed"
    assert terminated == [process]


def test_run_bounded_verifier_handles_immediate_deadline(tmp_path, monkeypatch):
    verifier = _python_verifier(tmp_path / "verifier", "import time\ntime.sleep(30)\n")
    monkeypatch.setattr(handoff, "VERIFIER_TIMEOUT_SECONDS", 0)

    with pytest.raises(handoff.HandoffError) as error:
        handoff._run_bounded_verifier(verifier, tmp_path / "readiness.json")

    assert error.value.error_code == "disksage-verifier-timeout"


def test_run_bounded_verifier_retries_nonblocking_read(tmp_path, monkeypatch):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    original_selector = handoff.selectors.DefaultSelector
    original_read = handoff.os.read
    state = {"block_next_read": False, "injected": False}

    class BlockingOnceSelector:
        def __init__(self):
            self.delegate = original_selector()

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def select(self, *args, **kwargs):
            events = self.delegate.select(*args, **kwargs)
            if events and not state["injected"]:
                state["injected"] = True
                state["block_next_read"] = True
            return events

    def read_once_blocking(file_descriptor, size):
        if state["block_next_read"]:
            state["block_next_read"] = False
            raise BlockingIOError
        return original_read(file_descriptor, size)

    monkeypatch.setattr(handoff.selectors, "DefaultSelector", BlockingOnceSelector)
    monkeypatch.setattr(handoff.os, "read", read_once_blocking)

    result = handoff._run_bounded_verifier(verifier, tmp_path / "readiness.json")

    assert state["injected"]
    assert handoff._decode_protocol(result) == _success_payload()


def test_run_bounded_verifier_rejects_deadline_after_stream_drain(
    tmp_path, monkeypatch
):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    original_selector = handoff.selectors.DefaultSelector
    state = {"streams_drained": False}

    class DrainAwareSelector:
        def __init__(self):
            self.delegate = original_selector()

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def get_map(self):
            mapping = self.delegate.get_map()
            if not mapping:
                state["streams_drained"] = True
            return mapping

    def monotonic():
        return 100.0 if state["streams_drained"] else 0.0

    monkeypatch.setattr(handoff.selectors, "DefaultSelector", DrainAwareSelector)
    monkeypatch.setattr(handoff, "monotonic", monotonic)

    with pytest.raises(handoff.HandoffError) as error:
        handoff._run_bounded_verifier(verifier, tmp_path / "readiness.json")

    assert error.value.error_code == "disksage-verifier-timeout"


def test_run_bounded_verifier_normalizes_wait_timeout(tmp_path, monkeypatch):
    verifier = _json_verifier(tmp_path / "verifier", _success_payload(), 0)
    original_popen = handoff.subprocess.Popen

    class WaitTimeoutOnce:
        def __init__(self, delegate):
            self.delegate = delegate
            self.timed_out = False

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def wait(self, timeout):
            if not self.timed_out:
                self.timed_out = True
                raise subprocess.TimeoutExpired("verifier", timeout)
            return self.delegate.wait(timeout=timeout)

    def wrapped_popen(*args, **kwargs):
        return WaitTimeoutOnce(original_popen(*args, **kwargs))

    monkeypatch.setattr(handoff.subprocess, "Popen", wrapped_popen)

    with pytest.raises(handoff.HandoffError) as error:
        handoff._run_bounded_verifier(verifier, tmp_path / "readiness.json")

    assert error.value.error_code == "disksage-verifier-timeout"


@pytest.mark.parametrize(
    ("payload", "exit_code"),
    [
        ({**_success_payload(), "private_path": "/private/source"}, 0),
        ({"ok": False, "error_code": "invalid"}, 0),
        (_success_payload(), 65),
        ({"ok": False, "error_code": "invalid/path"}, 65),
        (_success_payload(), 23),
    ],
)
def test_main_rejects_mismatched_or_extended_protocol_without_leakage(
    tmp_path, capsys, payload, exit_code
):
    verifier = _json_verifier(tmp_path / "verifier", payload, exit_code)
    readiness = tmp_path / "private-readiness.json"

    assert handoff.main(_handoff_args(verifier, readiness)) == 70
    encoded = capsys.readouterr().out
    assert json.loads(encoded) == {
        "ok": False,
        "error_code": "disksage-verifier-protocol-invalid",
    }
    assert "/private/source" not in encoded
    assert str(readiness) not in encoded


@pytest.mark.parametrize(
    "result",
    [
        handoff.VerifierResult(0, b"not-json", b""),
        handoff.VerifierResult(0, b"\xff", b""),
        handoff.VerifierResult(0, b"[]", b""),
        handoff.VerifierResult(0, b"{}", b""),
        handoff.VerifierResult(0, json.dumps(_success_payload()).encode(), b"warning"),
        handoff.VerifierResult(
            0,
            json.dumps({**_success_payload(), "candidate_count": True}).encode(),
            b"",
        ),
    ],
)
def test_protocol_decoder_rejects_invalid_or_ambiguous_transport(result):
    with pytest.raises(handoff.HandoffError) as error:
        handoff._decode_protocol(result)

    assert error.value.error_code == "disksage-verifier-protocol-invalid"


@pytest.mark.parametrize("stream_name", ["stdout", "stderr"])
def test_main_kills_oversized_output_without_echoing_it(tmp_path, capsys, stream_name):
    verifier = _python_verifier(
        tmp_path / "verifier",
        "import sys\n"
        f"sys.{stream_name}.buffer.write(b'sensitive-path' * 7000)\n"
        f"sys.{stream_name}.flush()\n",
    )
    readiness = tmp_path / "readiness.json"

    assert handoff.main(_handoff_args(verifier, readiness)) == 70
    encoded = capsys.readouterr().out
    assert json.loads(encoded) == {
        "ok": False,
        "error_code": "disksage-verifier-output-too-large",
    }
    assert "sensitive-path" not in encoded


def test_main_kills_original_process_group_on_timeout(tmp_path, monkeypatch, capsys):
    child_pid_path = tmp_path / "child.pid"
    verifier = tmp_path / "verifier"
    verifier.write_text(
        "#!/bin/sh\n"
        "/bin/sleep 30 &\n"
        "child=$!\n"
        f"/usr/bin/printf '%s' \"$child\" > {shlex.quote(str(child_pid_path))}\n"
        'wait "$child"\n',
        encoding="utf-8",
    )
    verifier.chmod(0o700)
    readiness = tmp_path / "readiness.json"
    monkeypatch.setattr(handoff, "VERIFIER_TIMEOUT_SECONDS", 2)

    assert handoff.main(_handoff_args(verifier, readiness)) == 70
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-timeout",
    }
    child_pid = int(child_pid_path.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail("verifier process-group member survived timeout kill")


def test_cli_reserializes_rust_protocol_instead_of_forwarding_raw_output(tmp_path):
    payload = {
        "ok": False,
        "error_code": "naruon-copy-readiness-fingerprint-invalid",
    }
    verifier = _json_verifier(tmp_path / "fake-disksage-verifier", payload, 65)
    readiness = tmp_path / "readiness.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--verifier",
            str(verifier),
            "--verifier-sha256",
            _verifier_sha256(verifier),
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 65
    assert json.loads(result.stdout) == payload
    assert result.stderr == ""


def test_script_entrypoint_exits_through_redacted_usage_protocol(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH)])

    with pytest.raises(SystemExit) as exit_status:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exit_status.value.code == 64
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-handoff-usage-invalid",
    }
