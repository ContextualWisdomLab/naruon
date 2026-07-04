#!/usr/bin/env python3
"""Verify a copied Naruon evidence snapshot digest without server access."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

DIGEST_EXCLUDED_FIELDS = {
    "snapshot_digest",
    "digest_algorithm",
    "canonical_payload_fields",
}
SUPPORTED_ALGORITHM = "sha256"


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    exit_code: int
    digest_algorithm: str | None
    expected_digest: str | None
    actual_digest: str | None
    canonical_payload_fields: list[str]
    error_code: str | None = None

    def to_output(self) -> dict[str, object]:
        output: dict[str, object] = {
            "ok": self.ok,
            "digest_algorithm": self.digest_algorithm,
            "expected_digest": self.expected_digest,
            "actual_digest": self.actual_digest,
            "canonical_payload_fields": self.canonical_payload_fields,
        }
        if self.error_code is not None:
            output["error_code"] = self.error_code
        return output


def _digest_payload(snapshot: dict[str, object]) -> dict[str, object]:
    payload = dict(snapshot)
    for field_name in DIGEST_EXCLUDED_FIELDS:
        payload.pop(field_name, None)
    return payload


def _sha256_digest(payload: dict[str, object]) -> str:
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()


def verify_snapshot_payload(snapshot: dict[str, object]) -> VerificationResult:
    expected_digest = snapshot.get("snapshot_digest")
    digest_algorithm = snapshot.get("digest_algorithm")
    if not isinstance(expected_digest, str) or not expected_digest:
        return VerificationResult(
            ok=False,
            exit_code=2,
            digest_algorithm=digest_algorithm if isinstance(digest_algorithm, str) else None,
            expected_digest=None,
            actual_digest=None,
            canonical_payload_fields=[],
            error_code="missing_snapshot_digest",
        )
    if digest_algorithm != SUPPORTED_ALGORITHM:
        return VerificationResult(
            ok=False,
            exit_code=3,
            digest_algorithm=digest_algorithm if isinstance(digest_algorithm, str) else None,
            expected_digest=expected_digest,
            actual_digest=None,
            canonical_payload_fields=[],
            error_code="unsupported_digest_algorithm",
        )

    payload = _digest_payload(snapshot)
    actual_digest = _sha256_digest(payload)
    canonical_payload_fields = sorted(payload)
    digest_matches = actual_digest == expected_digest
    return VerificationResult(
        ok=digest_matches,
        exit_code=0 if digest_matches else 4,
        digest_algorithm=SUPPORTED_ALGORITHM,
        expected_digest=expected_digest,
        actual_digest=actual_digest,
        canonical_payload_fields=canonical_payload_fields,
        error_code=None if digest_matches else "digest_mismatch",
    )


def _read_snapshot(source: str) -> dict[str, object] | None:
    try:
        raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        loaded: Any = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a copied Naruon evidence snapshot SHA-256 digest.",
    )
    parser.add_argument("snapshot", help="Snapshot JSON file path, or '-' for stdin.")
    args = parser.parse_args(argv)

    snapshot = _read_snapshot(args.snapshot)
    if snapshot is None:
        _print_json({"ok": False, "error_code": "invalid_json"})
        return 1

    result = verify_snapshot_payload(snapshot)
    _print_json(result.to_output())
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
