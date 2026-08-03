#!/usr/bin/env python3
"""Delegate a readiness envelope to DiskSage's offline Rust verifier."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
from typing import NoReturn


VERIFIER_TIMEOUT_SECONDS = 10
MAX_STDOUT_BYTES = 64 * 1024
MAX_STDERR_BYTES = 8 * 1024
EXIT_USAGE = 64
EXIT_VERIFIER_UNAVAILABLE = 66
EXIT_EXECUTION_FAILED = 70

SUCCESS_FIELDS = frozenset(
    {
        "ok",
        "schema_kind",
        "schema_version",
        "provider",
        "readiness_state",
        "candidate_count",
        "candidate_bytes",
        "readiness_fingerprint_sha256",
        "local_paths_included",
        "relative_names_included",
        "raw_metadata_values_included",
        "cloud_write_executed",
        "source_eviction_authorized",
    }
)
FAILURE_FIELDS = frozenset({"ok", "error_code"})
FALSE_CLAIM_FIELDS = (
    "local_paths_included",
    "relative_names_included",
    "raw_metadata_values_included",
    "cloud_write_executed",
    "source_eviction_authorized",
)
PROVIDERS = frozenset({"icloud", "onedrive", "google-drive"})
READINESS_STATES = frozenset(
    {"no-candidates", "blocked", "partially-ready", "ready-without-new-review"}
)
ERROR_CODE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class HandoffError(Exception):
    def __init__(self, error_code: str, exit_code: int = EXIT_EXECUTION_FAILED):
        super().__init__(error_code)
        self.error_code = error_code
        self.exit_code = exit_code


class HandoffArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> NoReturn:
        raise HandoffError("disksage-handoff-usage-invalid", EXIT_USAGE)


@dataclass(frozen=True)
class VerifierResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _verifier_is_executable_regular_file(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and os.access(path, os.X_OK)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    elif process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
    except OSError:
        pass


def _run_bounded_verifier(verifier: Path, readiness: Path) -> VerifierResult:
    try:
        process = subprocess.Popen(
            [str(verifier), str(readiness)],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/",
            env={},
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        raise HandoffError("disksage-verifier-exec-failed") from error

    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    streams = {
        "stdout": (process.stdout, MAX_STDOUT_BYTES),
        "stderr": (process.stderr, MAX_STDERR_BYTES),
    }
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + VERIFIER_TIMEOUT_SECONDS
    try:
        for name, (stream, _limit) in streams.items():
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HandoffError("disksage-verifier-timeout")
            events = selector.select(timeout=remaining)
            if not events:
                raise HandoffError("disksage-verifier-timeout")
            for key, _mask in events:
                name = key.data
                stream, limit = streams[name]
                read_size = min(8192, limit - len(buffers[name]) + 1)
                try:
                    chunk = os.read(stream.fileno(), read_size)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                buffers[name].extend(chunk)
                if len(buffers[name]) > limit:
                    raise HandoffError("disksage-verifier-output-too-large")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HandoffError("disksage-verifier-timeout")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise HandoffError("disksage-verifier-timeout") from error
    except HandoffError:
        _terminate_process_group(process)
        raise
    except OSError as error:
        _terminate_process_group(process)
        raise HandoffError("disksage-verifier-exec-failed") from error
    finally:
        selector.close()
        for stream, _limit in streams.values():
            if not stream.closed:
                stream.close()

    # A verifier is not permitted to leave background descendants behind.
    _terminate_process_group(process)
    return VerifierResult(
        returncode=returncode,
        stdout=bytes(buffers["stdout"]),
        stderr=bytes(buffers["stderr"]),
    )


def _is_lower_hex_64(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _decode_protocol(result: VerifierResult) -> dict[str, object]:
    if result.stderr:
        raise HandoffError("disksage-verifier-protocol-invalid")
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise HandoffError("disksage-verifier-protocol-invalid") from error
    if type(payload) is not dict:
        raise HandoffError("disksage-verifier-protocol-invalid")

    if result.returncode == 0:
        valid = (
            frozenset(payload) == SUCCESS_FIELDS
            and payload.get("ok") is True
            and payload.get("schema_kind") == "disksage.naruon.cloud-copy-readiness"
            and type(payload.get("schema_version")) is int
            and payload.get("schema_version") == 3
            and payload.get("provider") in PROVIDERS
            and payload.get("readiness_state") in READINESS_STATES
            and type(payload.get("candidate_count")) is int
            and payload["candidate_count"] >= 0
            and type(payload.get("candidate_bytes")) is int
            and payload["candidate_bytes"] >= 0
            and _is_lower_hex_64(payload.get("readiness_fingerprint_sha256"))
            and all(payload.get(field) is False for field in FALSE_CLAIM_FIELDS)
        )
    elif result.returncode in (64, 65):
        error_code = payload.get("error_code")
        valid = (
            frozenset(payload) == FAILURE_FIELDS
            and payload.get("ok") is False
            and type(error_code) is str
            and len(error_code) <= 128
            and ERROR_CODE_PATTERN.fullmatch(error_code) is not None
        )
    else:
        valid = False
    if not valid:
        raise HandoffError("disksage-verifier-protocol-invalid")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = HandoffArgumentParser(
        description=(
            "Verify a DiskSage Naruon cloud-copy readiness envelope with the "
            "DiskSage Rust verifier."
        )
    )
    parser.add_argument(
        "--verifier",
        required=True,
        help="Absolute path to disksage-naruon-copy-readiness-verify.",
    )
    parser.add_argument("readiness", help="Absolute readiness JSON file path.")
    try:
        args = parser.parse_args(argv)
        verifier = Path(args.verifier)
        readiness = Path(args.readiness)
        if not _verifier_is_executable_regular_file(verifier):
            raise HandoffError(
                "disksage-verifier-unavailable", EXIT_VERIFIER_UNAVAILABLE
            )
        if not readiness.is_absolute():
            raise HandoffError(
                "naruon-copy-readiness-input-path-not-absolute", EXIT_USAGE
            )
        result = _run_bounded_verifier(verifier, readiness)
        payload = _decode_protocol(result)
    except HandoffError as error:
        _print_json({"ok": False, "error_code": error.error_code})
        return error.exit_code

    _print_json(payload)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
