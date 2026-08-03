import json
import os
from pathlib import Path
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

    assert handoff.main(["--verifier", str(verifier), str(readiness)]) == 0
    assert json.loads(capsys.readouterr().out) == _success_payload()
    assert not (tmp_path / "must-not-exist").exists()


@pytest.mark.parametrize("exit_code", [64, 65])
def test_main_preserves_valid_disksage_failure_protocol(tmp_path, capsys, exit_code):
    payload = {
        "ok": False,
        "error_code": "naruon-copy-readiness-fingerprint-invalid",
    }
    verifier = _json_verifier(tmp_path / "verifier", payload, exit_code)
    readiness = tmp_path / "readiness.json"

    assert handoff.main(["--verifier", str(verifier), str(readiness)]) == exit_code
    assert json.loads(capsys.readouterr().out) == payload


def test_main_rejects_relative_or_untrusted_paths(tmp_path, capsys):
    readiness = tmp_path / "readiness.json"
    target = _json_verifier(tmp_path / "target", _success_payload(), 0)
    non_executable = tmp_path / "non-executable"
    non_executable.write_text("not executable", encoding="utf-8")
    directory = tmp_path / "directory"
    directory.mkdir()
    symlink = tmp_path / "verifier-link"
    symlink.symlink_to(target)

    assert handoff.main(["--verifier", "relative", str(readiness)]) == 66
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-unavailable",
    }
    assert handoff.main(["--verifier", str(symlink), str(readiness)]) == 66
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "disksage-verifier-unavailable",
    }
    for invalid_verifier in (non_executable, directory):
        assert handoff.main(["--verifier", str(invalid_verifier), str(readiness)]) == 66
        assert json.loads(capsys.readouterr().out) == {
            "ok": False,
            "error_code": "disksage-verifier-unavailable",
        }
    assert handoff.main(["--verifier", str(target), "private.json"]) == 64
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error_code": "naruon-copy-readiness-input-path-not-absolute",
    }


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

    assert handoff.main(["--verifier", str(verifier), str(readiness)]) == 70
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

    assert handoff.main(["--verifier", str(verifier), str(readiness)]) == 70
    encoded = capsys.readouterr().out
    assert json.loads(encoded) == {
        "ok": False,
        "error_code": "disksage-verifier-output-too-large",
    }
    assert "sensitive-path" not in encoded


def test_main_kills_process_group_on_timeout(tmp_path, monkeypatch, capsys):
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

    assert handoff.main(["--verifier", str(verifier), str(readiness)]) == 70
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
        pytest.fail("verifier descendant survived process-group timeout kill")


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
            str(readiness),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 65
    assert json.loads(result.stdout) == payload
    assert result.stderr == ""
