#!/usr/bin/env python3
"""Validate hash-pinned Python locks against exact PyPI release metadata.

This validator is intentionally narrower than dependency installation. It proves
that each exact project/version pin has at least one eligible, non-yanked wheel
or source distribution published by PyPI whose SHA-256 digest is recorded in
the lock. It does not claim platform compatibility, dependency closure, install
success, private-index parity, or artifact-attestation identity.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterable, Mapping

SCHEMA_VERSION = "naruon.python-lock-registry-provenance.v1"
DEFAULT_PYPI_ORIGIN = "https://pypi.org"
MAX_METADATA_BYTES = 4 * 1024 * 1024
ALLOWED_PACKAGE_TYPES = frozenset({"bdist_wheel", "sdist"})
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_EXACT_PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9._,-]+\])?)"
    r"==(?P<version>[^\s\\;]+)(?:\s*;\s*[^\\]+)?\s*\\?$"
)
_HASH_LINE_RE = re.compile(r"^--hash=sha256:(?P<digest>[0-9a-fA-F]{64})\s*\\?$")

ReleaseFetcher = Callable[[str, str], Mapping[str, object]]


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from contacting an unvalidated redirect target."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        """Reject every redirect so the caller can fail before a second request."""
        return None


def _open_pypi_request(
    request: urllib.request.Request,
    *,
    timeout_seconds: float,
) -> object:
    """Open one PyPI request without following redirects."""
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        return opener.open(request, timeout=timeout_seconds)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise ValueError("PyPI metadata redirects are not allowed") from exc
        raise


def _normalized_name(name: str) -> str:
    """Return the canonical comparison and PyPI lookup form for a project name."""
    return re.sub(r"[-_.]+", "-", name.split("[", 1)[0].lower())


def _relative_path(path: Path, repository_root: Path) -> str:
    """Return a stable repository-relative path without leaking runner paths."""
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _resolve_repository_path(path: Path, repository_root: Path) -> Path | None:
    """Resolve ``path`` only when its final target remains inside the repository."""
    root = repository_root.resolve()
    candidate = path.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _violation(code: str, path: str, detail: str) -> dict[str, str]:
    """Build one deterministic machine-readable validation finding."""
    return {"code": code, "path": path, "detail": detail}


def _parse_lock_requirements(
    text: str,
    relative_path: str,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """Parse exact requirements and their attached SHA-256 values from a lock."""
    requirements: list[dict[str, object]] = []
    violations: list[dict[str, str]] = []
    current: dict[str, object] | None = None

    def finalize() -> None:
        nonlocal current
        if current is None:
            return
        hashes = current["hashes"]
        assert isinstance(hashes, set)
        if not hashes:
            violations.append(
                _violation(
                    "lock-requirement-has-no-sha256",
                    relative_path,
                    f"{current['project']}=={current['version']} has no SHA-256",
                )
            )
        current["hashes"] = sorted(hashes)
        requirements.append(current)
        current = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        hash_match = _HASH_LINE_RE.fullmatch(stripped)
        if hash_match is not None:
            if current is None:
                violations.append(
                    _violation(
                        "lock-orphan-sha256",
                        relative_path,
                        "SHA-256 entry is not attached to an exact requirement",
                    )
                )
            else:
                hashes = current["hashes"]
                assert isinstance(hashes, set)
                hashes.add(hash_match.group("digest").lower())
            continue
        if stripped.startswith("-"):
            continue

        finalize()
        match = _EXACT_PIN_RE.fullmatch(stripped)
        if match is None:
            violations.append(
                _violation(
                    "lock-requirement-not-exact",
                    relative_path,
                    "lock contains a requirement that is not an exact == pin",
                )
            )
            continue
        current = {
            "project": _normalized_name(match.group("name")),
            "version": match.group("version"),
            "hashes": set(),
        }

    finalize()
    return requirements, violations


def build_pypi_release_url(
    project: str,
    version: str,
    *,
    pypi_origin: str = DEFAULT_PYPI_ORIGIN,
) -> str:
    """Build an exact PyPI release JSON URL from a credential-free HTTPS origin."""
    try:
        parsed = urllib.parse.urlsplit(pypi_origin)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("pypi_origin must be the trusted PyPI origin") from exc
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "pypi.org"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("pypi_origin must be the trusted PyPI origin")

    normalized_project = _normalized_name(project)
    project_segment = urllib.parse.quote(normalized_project, safe="-._")
    version_segment = urllib.parse.quote(version, safe="-._")
    return f"{DEFAULT_PYPI_ORIGIN}/pypi/{project_segment}/{version_segment}/json"


def fetch_pypi_release(
    project: str,
    version: str,
    *,
    timeout_seconds: float = 15.0,
    max_metadata_bytes: int = MAX_METADATA_BYTES,
) -> Mapping[str, object]:
    """Fetch one exact PyPI release document with a bounded credential-free GET."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_metadata_bytes <= 0:
        raise ValueError("max_metadata_bytes must be positive")

    release_url = build_pypi_release_url(project, version)
    request = urllib.request.Request(
        release_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "naruon-lock-provenance/1",
        },
        method="GET",
    )
    with _open_pypi_request(request, timeout_seconds=timeout_seconds) as response:
        final_url_getter = getattr(response, "geturl", None)
        final_url = final_url_getter() if callable(final_url_getter) else release_url
        if final_url != release_url:
            raise ValueError("PyPI metadata response left the trusted PyPI origin")
        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            raise ValueError("PyPI release metadata must be JSON")
        payload = response.read(max_metadata_bytes + 1)
    if len(payload) > max_metadata_bytes:
        raise ValueError("PyPI release metadata exceeds the configured byte limit")
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("PyPI release metadata must be a JSON object")
    return decoded


def _eligible_registry_hashes(metadata: Mapping[str, object]) -> set[str]:
    """Return non-yanked wheel/sdist SHA-256 values from a PyPI release payload."""
    urls = metadata.get("urls")
    if not isinstance(urls, list):
        return set()
    hashes: set[str] = set()
    for artifact in urls:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("yanked") is True:
            continue
        if artifact.get("packagetype") not in ALLOWED_PACKAGE_TYPES:
            continue
        digests = artifact.get("digests")
        if not isinstance(digests, dict):
            continue
        digest = digests.get("sha256")
        if isinstance(digest, str) and _SHA256_RE.fullmatch(digest):
            hashes.add(digest.lower())
    return hashes


def _validate_requirement_metadata(
    *,
    project: str,
    version: str,
    locked_hashes: set[str],
    metadata: Mapping[str, object],
    relative_path: str,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    """Compare one exact lock pin with one exact PyPI release metadata document."""
    violations: list[dict[str, str]] = []
    info = metadata.get("info")
    info_mapping = info if isinstance(info, dict) else {}
    metadata_name = info_mapping.get("name")
    metadata_version = info_mapping.get("version")
    if not isinstance(metadata_name, str) or _normalized_name(metadata_name) != project:
        violations.append(
            _violation(
                "registry-project-mismatch",
                relative_path,
                f"trusted metadata identity does not match {project}",
            )
        )
    if not isinstance(metadata_version, str) or metadata_version != version:
        violations.append(
            _violation(
                "registry-version-mismatch",
                relative_path,
                f"trusted metadata version does not match {project}=={version}",
            )
        )

    matched_count = 0
    if not violations:
        registry_hashes = _eligible_registry_hashes(metadata)
        if not registry_hashes:
            violations.append(
                _violation(
                    "registry-release-has-no-allowed-artifacts",
                    relative_path,
                    f"{project}=={version} has no eligible non-yanked wheel or sdist SHA-256",
                )
            )
        else:
            matched_count = len(locked_hashes & registry_hashes)
            if matched_count == 0:
                violations.append(
                    _violation(
                        "registry-hash-mismatch",
                        relative_path,
                        f"{project}=={version} lock hashes do not match eligible PyPI artifacts",
                    )
                )

    requirement_receipt = {
        "project": project,
        "version": version,
        "status": "failed" if violations else "passed",
        "matched_artifact_count": matched_count,
    }
    return requirement_receipt, violations


def validate_lock_against_registry(
    lock_path: Path,
    repository_root: Path,
    *,
    fetch_release: ReleaseFetcher = fetch_pypi_release,
) -> dict[str, object]:
    """Validate one in-repository hash lock against exact PyPI release metadata."""
    relative_path = _relative_path(lock_path, repository_root)
    resolved_lock = _resolve_repository_path(lock_path, repository_root)
    if resolved_lock is None:
        violations = [
            _violation(
                "lock-path-outside-repository",
                relative_path,
                "lock path resolves outside repository root",
            )
        ]
        return {
            "path": relative_path,
            "status": "failed",
            "requirements": [],
            "violations": violations,
        }

    try:
        text = resolved_lock.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        violations = [
            _violation(
                "lock-read-failed",
                relative_path,
                "lock could not be read as repository UTF-8 text",
            )
        ]
        return {
            "path": relative_path,
            "status": "failed",
            "requirements": [],
            "violations": violations,
        }

    parsed_requirements, violations = _parse_lock_requirements(text, relative_path)
    requirement_receipts: list[dict[str, object]] = []
    for requirement in parsed_requirements:
        project = str(requirement["project"])
        version = str(requirement["version"])
        raw_hashes = requirement["hashes"]
        assert isinstance(raw_hashes, list)
        locked_hashes = {str(value).lower() for value in raw_hashes}
        try:
            metadata = fetch_release(project, version)
        except Exception:
            requirement_receipts.append(
                {
                    "project": project,
                    "version": version,
                    "status": "failed",
                    "matched_artifact_count": 0,
                }
            )
            violations.append(
                _violation(
                    "registry-metadata-fetch-failed",
                    relative_path,
                    f"trusted PyPI metadata could not be resolved for {project}=={version}",
                )
            )
            continue
        requirement_receipt, metadata_violations = _validate_requirement_metadata(
            project=project,
            version=version,
            locked_hashes=locked_hashes,
            metadata=metadata,
            relative_path=relative_path,
        )
        requirement_receipts.append(requirement_receipt)
        violations.extend(metadata_violations)

    requirement_receipts.sort(key=lambda item: (str(item["project"]), str(item["version"])))
    violations.sort(key=lambda item: (item["code"], item["path"], item["detail"]))
    return {
        "path": relative_path,
        "status": "failed" if violations else "passed",
        "requirements": requirement_receipts,
        "violations": violations,
    }


def discover_hash_locks(repository_root: Path) -> list[Path]:
    """Discover active requirements hash locks without reading escaping symlinks."""
    candidates: list[Path] = []
    for path in repository_root.rglob("requirements*.txt"):
        if any(part in {".git", ".venv", "node_modules"} for part in path.parts):
            continue
        resolved = _resolve_repository_path(path, repository_root)
        if resolved is None:
            candidates.append(path)
            continue
        try:
            text = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if "--hash=sha256:" in text or "hash" in path.stem.lower():
            candidates.append(path)
    return sorted(candidates, key=lambda path: _relative_path(path, repository_root))


def validate_repository_registry(
    repository_root: Path,
    *,
    fetch_release: ReleaseFetcher = fetch_pypi_release,
) -> dict[str, object]:
    """Validate all active hash locks while resolving each release metadata once."""
    cache: dict[tuple[str, str], tuple[bool, Mapping[str, object] | None]] = {}

    def cached_fetch(project: str, version: str) -> Mapping[str, object]:
        key = (project, version)
        cached = cache.get(key)
        if cached is None:
            try:
                metadata = fetch_release(project, version)
            except Exception:
                cache[key] = (False, None)
                raise RuntimeError("registry metadata unavailable") from None
            cache[key] = (True, metadata)
            return metadata
        success, metadata = cached
        if not success or metadata is None:
            raise RuntimeError("registry metadata unavailable")
        return metadata

    discovered_locks = discover_hash_locks(repository_root)
    lock_receipts = [
        validate_lock_against_registry(path, repository_root, fetch_release=cached_fetch)
        for path in discovered_locks
    ]
    violations = [
        violation
        for receipt in lock_receipts
        for violation in receipt["violations"]
        if isinstance(violation, dict)
    ]
    if not discovered_locks:
        violations.append(
            _violation(
                "registry-no-hash-locks",
                ".",
                "no active Python requirements hash lock was discovered",
            )
        )
    violations.sort(key=lambda item: (item["code"], item["path"], item["detail"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed" if violations else "passed",
        "lock_files": lock_receipts,
        "violations": violations,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for repository-level registry validation."""
    parser = argparse.ArgumentParser(
        description="Verify Python lock SHA-256 values against exact PyPI releases."
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to validate (default: current working directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one deterministic credential-free JSON receipt.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Run registry validation and return zero only for a passing receipt."""
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    receipt = validate_repository_registry(args.repository_root)
    if args.json:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    else:
        print(f"Python lock PyPI provenance: {receipt['status']}")
        for violation in receipt["violations"]:
            print(f"{violation['code']}: {violation['path']}: {violation['detail']}")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
