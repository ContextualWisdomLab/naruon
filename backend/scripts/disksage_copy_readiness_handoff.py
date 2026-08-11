#!/usr/bin/env python3
"""Delegate a readiness envelope to DiskSage's offline Rust verifier."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import sys

# Bandit B404: subprocess is required for the digest-bound verifier process boundary.
import subprocess  # nosec B404
import tempfile
from time import monotonic
from typing import NoReturn


VERIFIER_TIMEOUT_SECONDS = 10
MAX_VERIFIER_BYTES = 256 * 1024 * 1024
VERIFIER_COPY_CHUNK_BYTES = 1024 * 1024
MAX_STDOUT_BYTES = 64 * 1024
MAX_STDERR_BYTES = 8 * 1024
VERIFIER_ENV = {
    "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath))
}
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
    """Carry a redacted stable error code and process exit status to the CLI boundary."""

    def __init__(self, error_code: str, exit_code: int = EXIT_EXECUTION_FAILED):
        super().__init__(error_code)
        self.error_code = error_code
        self.exit_code = exit_code


class HandoffArgumentParser(argparse.ArgumentParser):
    """Convert argparse diagnostics into the handoff's fixed redacted error protocol."""

    def error(self, _message: str) -> NoReturn:
        raise HandoffError("disksage-handoff-usage-invalid", EXIT_USAGE)


@dataclass(frozen=True)
class VerifierResult:
    """Hold bounded verifier transport output before strict protocol decoding."""

    returncode: int
    stdout: bytes
    stderr: bytes


def _print_json(payload: dict[str, object]) -> None:
    """Serialize one deterministic JSON object to the operator-facing stdout channel."""

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _verifier_is_executable_regular_file(path: Path) -> bool:
    """Preflight an absolute, non-symlink, executable regular verifier path."""

    if not path.is_absolute():
        return False
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and os.access(path, os.X_OK)


@contextmanager
def _verified_verifier_snapshot(path: Path, expected_sha256: str) -> Iterator[Path]:
    """Snapshot a fully materialized local verifier and bind its bytes to a digest."""
    if not _verifier_is_executable_regular_file(path):
        raise HandoffError("disksage-verifier-unavailable", EXIT_VERIFIER_UNAVAILABLE)

    open_flags = os.O_RDONLY
    open_flags |= getattr(os, "O_CLOEXEC", 0)
    open_flags |= getattr(os, "O_NOFOLLOW", 0)
    open_flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        source_fd = os.open(path, open_flags)
    except OSError as error:
        raise HandoffError(
            "disksage-verifier-unavailable", EXIT_VERIFIER_UNAVAILABLE
        ) from error

    try:
        source_metadata = os.fstat(source_fd)
        if (
            not stat.S_ISREG(source_metadata.st_mode)
            or source_metadata.st_mode & 0o111 == 0
            or source_metadata.st_size > MAX_VERIFIER_BYTES
        ):
            raise HandoffError(
                "disksage-verifier-unavailable", EXIT_VERIFIER_UNAVAILABLE
            )

        try:
            snapshot_directory = tempfile.TemporaryDirectory(
                prefix="naruon-disksage-verifier-"
            )
        except OSError as error:
            raise HandoffError("disksage-verifier-snapshot-failed") from error

        try:
            snapshot = Path(snapshot_directory.name) / "verifier"
            digest = hashlib.sha256()
            copied_bytes = 0
            try:
                with snapshot.open("xb", buffering=0) as destination:
                    while True:
                        chunk = os.read(source_fd, VERIFIER_COPY_CHUNK_BYTES)
                        if not chunk:
                            break
                        copied_bytes += len(chunk)
                        if copied_bytes > MAX_VERIFIER_BYTES:
                            raise HandoffError(
                                "disksage-verifier-unavailable",
                                EXIT_VERIFIER_UNAVAILABLE,
                            )
                        pending = memoryview(chunk)
                        while pending:
                            written = destination.write(pending)
                            if (
                                written is None
                                or written <= 0
                                or written > len(pending)
                            ):
                                raise OSError(
                                    "verifier snapshot write made no progress"
                                )
                            pending = pending[written:]
                        digest.update(chunk)
                    os.fsync(destination.fileno())
                snapshot.chmod(stat.S_IRUSR | stat.S_IXUSR)
            except HandoffError:
                raise
            except OSError as error:
                raise HandoffError("disksage-verifier-snapshot-failed") from error

            if digest.hexdigest() != expected_sha256:
                raise HandoffError(
                    "disksage-verifier-provenance-mismatch",
                    EXIT_VERIFIER_UNAVAILABLE,
                )
            yield snapshot
        finally:
            try:
                snapshot_directory.cleanup()
            except OSError as error:
                raise HandoffError("disksage-verifier-snapshot-failed") from error
    finally:
        try:
            os.close(source_fd)
        except OSError:
            # Preserve any earlier provenance or snapshot failure during best-effort teardown.
            pass


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    """Best-effort kill and reap the verifier's original process group."""

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            # The process group may already have exited before best-effort containment runs.
            pass
    elif process.poll() is None:
        try:
            process.kill()
        except OSError:
            # A concurrent exit makes the fallback kill unnecessary.
            pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                # The process may have exited between poll and the fallback kill.
                pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            # The bounded cleanup has exhausted its final reap attempt; never block the caller.
            pass
    except OSError:
        # A concurrently reaped process has already satisfied the teardown objective.
        pass


def _run_bounded_verifier(verifier: Path, readiness: Path) -> VerifierResult:
    """Run a digest-bound verifier snapshot with bounded time, output, and authority."""

    try:
        # Bandit B603: the executable is a digest-bound private snapshot and shell stays disabled.
        process = subprocess.Popen(  # nosec B603
            [str(verifier), str(readiness)],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/",
            env=VERIFIER_ENV,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        raise HandoffError("disksage-verifier-exec-failed") from error

    if process.stdout is None or process.stderr is None:
        _terminate_process_group(process)
        raise HandoffError("disksage-verifier-exec-failed")
    selector = selectors.DefaultSelector()
    streams = {
        "stdout": (process.stdout, MAX_STDOUT_BYTES),
        "stderr": (process.stderr, MAX_STDERR_BYTES),
    }
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = monotonic() + VERIFIER_TIMEOUT_SECONDS
    try:
        for name, (stream, _limit) in streams.items():
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - monotonic()
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

        remaining = deadline - monotonic()
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

    # Reap the verifier and kill anything left in its original process group.
    _terminate_process_group(process)
    return VerifierResult(
        returncode=returncode,
        stdout=bytes(buffers["stdout"]),
        stderr=bytes(buffers["stderr"]),
    )


def _is_lower_hex_64(value: object) -> bool:
    """Return whether a value is exactly one lowercase SHA-256 hexadecimal string."""

    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object while rejecting every duplicate member name."""

    payload: dict[str, object] = {}
    for name, value in pairs:
        if name in payload:
            raise ValueError("duplicate-json-object-name")
        payload[name] = value
    return payload


def _decode_protocol(result: VerifierResult) -> dict[str, object]:
    """Decode and validate the verifier's exact success or failure wire contract."""

    try:
        payload = json.loads(
            result.stdout.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise HandoffError("disksage-verifier-protocol-invalid") from error
    if type(payload) is not dict:
        raise HandoffError("disksage-verifier-protocol-invalid")

    if result.returncode == 0:
        valid = (
            not result.stderr
            and frozenset(payload) == SUCCESS_FIELDS
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
    """Validate CLI authority, run the verifier snapshot, and emit only safe JSON."""

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
    parser.add_argument(
        "--verifier-sha256",
        required=True,
        help=(
            "Expected lowercase SHA-256 of a fully materialized local DiskSage "
            "verifier approved by the operator or a trusted public evidence artifact."
        ),
    )
    parser.add_argument("readiness", help="Absolute readiness JSON file path.")
    try:
        args = parser.parse_args(argv)
        verifier = Path(args.verifier)
        readiness = Path(args.readiness)
        if not _is_lower_hex_64(args.verifier_sha256):
            raise HandoffError("disksage-verifier-sha256-invalid", EXIT_USAGE)
        if not readiness.is_absolute():
            raise HandoffError(
                "naruon-copy-readiness-input-path-not-absolute", EXIT_USAGE
            )
        with _verified_verifier_snapshot(
            verifier, args.verifier_sha256
        ) as verified_verifier:
            result = _run_bounded_verifier(verified_verifier, readiness)
            payload = _decode_protocol(result)
    except HandoffError as error:
        _print_json({"ok": False, "error_code": error.error_code})
        return error.exit_code

    _print_json(payload)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
