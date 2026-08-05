#!/usr/bin/env python3
"""Apply the bounded PR 1203 container-provenance repair.

The script is temporary branch machinery. It changes only reviewed container,
test, changelog, and doctoring paths; verifies exact predecessor fragments; and
is deleted by the one-shot workflow before the verified product commit is
published.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_NODE_DIGEST = "715e55e4b84e4bb0ff48e49b398a848f08e55daed8eb6a0ea1839ae53bc57583"
NEW_NODE_DIGEST = "deae974596a15b0b34dcfb4aa7e73347f41ec906e9580d950e55a0c335a3db1d"
OLD_OLLAMA_DIGEST = "6345fbc18bd73a1e16404be681dbc6fd291a027cab43ed541abe78c4c81051b0"
NEW_OLLAMA_DIGEST = "4dea9fb511947e24a84237bb636b0203abcb2ff0d3fbc7b4ff865deb91362131"


def replace_exact_count(path: str, old: str, new: str, expected_count: int) -> None:
    """Replace *expected_count* reviewed occurrences or verify the new state."""
    target = REPO_ROOT / path
    text = target.read_text(encoding="utf-8")
    old_count = text.count(old)
    if old_count == expected_count:
        target.write_text(text.replace(old, new), encoding="utf-8")
        return
    if old_count == 0 and text.count(new) >= expected_count:
        return
    raise SystemExit(
        f"{path}: expected {expected_count} old fragments or an already repaired "
        f"state; found old={old_count}, new={text.count(new)}"
    )


def update_base_image_pins() -> None:
    """Synchronize canonical Node and Ollama tag-and-digest references."""
    replace_exact_count("Dockerfile", OLD_NODE_DIGEST, NEW_NODE_DIGEST, 1)
    replace_exact_count("frontend/Dockerfile", OLD_NODE_DIGEST, NEW_NODE_DIGEST, 3)
    replace_exact_count("Dockerfile.ollama", OLD_OLLAMA_DIGEST, NEW_OLLAMA_DIGEST, 1)
    replace_exact_count(
        "backend/tests/test_repo_hygiene.py",
        OLD_OLLAMA_DIGEST,
        NEW_OLLAMA_DIGEST,
        1,
    )


def write_provenance_contract_tests() -> None:
    """Install deterministic tests for derived metadata and security pin drift."""
    target = REPO_ROOT / "backend/tests/test_container_provenance_contract.py"
    target.write_text(
        f'''"""Container provenance and immutable dependency regression contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_DIGEST = "{NEW_NODE_DIGEST}"
OLLAMA_DIGEST = "{NEW_OLLAMA_DIGEST}"


def read_text(relative_path: str) -> str:
    """Read a UTF-8 repository file by its stable relative path."""
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def first_base_reference(dockerfile: str) -> str:
    """Return the first non-option image reference from a Dockerfile."""
    for raw_line in dockerfile.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0].upper() != "FROM":
            continue
        index = 1
        while index < len(parts) and parts[index].startswith("--"):
            index += 1
        if index >= len(parts):
            raise AssertionError("FROM instruction has no image reference")
        return parts[index]
    raise AssertionError("Dockerfile has no FROM instruction")


def test_canonical_dockerfiles_use_synchronized_tag_and_digest_pins() -> None:
    """Shared runtimes and Ollama use exact reviewable multi-arch base pins."""
    root = read_text("Dockerfile")
    frontend = read_text("frontend/Dockerfile")
    connector = read_text("connector/Dockerfile")
    ollama = read_text("Dockerfile.ollama")

    root_python = first_base_reference(root)
    connector_python = first_base_reference(connector)
    node_match = re.search(
        r"^FROM (?P<reference>node:26-slim@sha256:[0-9a-f]{{64}}) "
        r"AS frontend-builder$",
        root,
        flags=re.MULTILINE,
    )

    assert re.fullmatch(r"python:3\.14-slim@sha256:[0-9a-f]{{64}}", root_python)
    assert connector_python == root_python
    assert node_match is not None
    assert node_match.group("reference") == f"node:26-slim@sha256:{{NODE_DIGEST}}"
    assert first_base_reference(frontend) == node_match.group("reference")
    assert first_base_reference(ollama) == f"ollama/ollama@sha256:{{OLLAMA_DIGEST}}"
    assert "FROM ollama/ollama:latest" not in ollama


def test_publish_workflow_derives_provenance_from_canonical_dockerfiles() -> None:
    """Release metadata and platform proof come from Dockerfiles, not constants."""
    workflow = read_text(".github/workflows/docker-publish.yml")

    assert workflow.count("base_dockerfile: Dockerfile") == 4
    assert workflow.count("base_dockerfile: frontend/Dockerfile") == 2
    assert workflow.count(
        'base_reference="$(awk \'toupper($1) == "FROM" {{ print $2; exit }}\' '
        '"$BASE_DOCKERFILE")"'
    ) == 2
    assert (
        'base_image="$(awk \'toupper($1) == "FROM" {{ print $2; exit }}\' '
        'Dockerfile.ollama)"'
    ) in workflow
    assert "for platform in linux/amd64 linux/arm64; do" in workflow
    assert "DOCKER_METADATA_ANNOTATIONS_LEVELS: manifest,index" in workflow
    assert NODE_DIGEST not in workflow
    assert OLLAMA_DIGEST not in workflow


def test_container_security_pins_cannot_regress_independently() -> None:
    """Container provenance changes preserve reviewed dependency security pins."""
    backend_requirements = read_text("backend/requirements.txt")
    strix_requirements = read_text("requirements-strix-ci.txt")
    frontend_manifest = json.loads(read_text("frontend/package.json"))
    frontend_lock = read_text("frontend/pnpm-lock.yaml")

    assert "protobuf==7.35.1" in backend_requirements
    assert "protobuf==6.33.6" in strix_requirements
    assert frontend_manifest["devDependencies"]["postcss"] == "8.5.24"
    assert frontend_manifest["devDependencies"]["jsdom"] == "^30.0.1"
    assert frontend_manifest["overrides"]["brace-expansion"] == "5.0.9"
    assert frontend_manifest["overrides"]["undici"] == "8.9.0"
    for exact_lock_entry in (
        "postcss@8.5.24",
        "jsdom@30.0.1",
        "brace-expansion@5.0.9",
        "undici@8.9.0",
    ):
        assert exact_lock_entry in frontend_lock
''',
        encoding="utf-8",
    )


def update_changelog() -> None:
    """Record the current container provenance and regression repair."""
    target = REPO_ROOT / "CHANGELOG.md"
    text = target.read_text(encoding="utf-8")
    section = f'''### 컨테이너 프로비넌스 및 베이스 이미지 정합성

- Node 26과 Ollama 생산 베이스를 reviewable tag+digest 형식의 현재 multi-architecture manifest(`sha256:{NEW_NODE_DIGEST}`, `sha256:{NEW_OLLAMA_DIGEST}`)로 동기화했습니다.
- OCI base name/digest annotation은 Dockerfile의 실제 첫 `FROM`에서 계산하고, Ollama의 `linux/amd64`·`linux/arm64` manifest 존재를 PR 이미지 검증에서 fail-closed로 확인합니다.
- Strix의 `protobuf==6.33.6`, backend의 `protobuf==7.35.1`, frontend의 `postcss==8.5.24`, `jsdom==30.0.1`, `brace-expansion==5.0.9`, `undici==8.9.0` 보안 핀이 컨테이너 갱신과 무관하게 퇴행하지 않도록 영구 계약 테스트를 추가했습니다.

'''
    if section in text:
        return
    marker = "## [Unreleased]\n"
    if text.count(marker) != 1:
        raise SystemExit("CHANGELOG.md: expected one Unreleased marker")
    target.write_text(text.replace(marker, marker + section, 1), encoding="utf-8")


def write_doctoring() -> None:
    """Write the standards, threat model, and verification record in APA 7th form."""
    doctoring_dir = REPO_ROOT / "docs/doctoring"
    doctoring_dir.mkdir(parents=True, exist_ok=True)
    target = doctoring_dir / "container-provenance-contract.md"
    target.write_text(
        f'''# Container provenance contract doctoring

## Decision

Naruon keeps a human-reviewable tag and a content-addressed `sha256` digest on
every production base image. Shared Python and Node runtimes are synchronized
across standalone images and the combined image. OCI
`org.opencontainers.image.base.name` and `.base.digest` annotations are derived
from the canonical Dockerfile's first `FROM` instruction; the workflow does not
duplicate digest constants. The Ollama base manifest must advertise both
`linux/amd64` and `linux/arm64` before a pull-request image build proceeds.

Current reviewed pins are Node `sha256:{NEW_NODE_DIGEST}` and Ollama
`sha256:{NEW_OLLAMA_DIGEST}`. A tag aids review, while the digest selects exact
content. Neither alone is treated as complete provenance.

## Threat model and limitations

This contract prevents mutable-tag drift, stale copied annotation values,
platform omission, and unrelated dependency-pin rollback in the reviewed
repository state. It does not claim that a digest is trustworthy merely because
it is immutable, nor does it attest who built the upstream image. Repository
workflow provenance and SBOM generation remain separate evidence and must pass
on the same pull-request head.

The implementation is aligned with the current OCI image and image-index model,
SLSA 1.2 source/build provenance concepts, in-toto supply-chain layout evidence,
and the final NIST SSDF 1.1 practice baseline. NIST SSDF 1.2 remains a draft and
is informative only; no unsupported formal-conformance claim is made.

## Verification contract

- Parse and compare canonical Dockerfile `FROM` references.
- Require exact tag-and-64-hex-digest syntax.
- Derive OCI base metadata from `BASE_DOCKERFILE` in both validation and release jobs.
- Resolve the pinned Ollama manifest and require amd64 and arm64 entries.
- Reject literal copied Node or Ollama digests in the publication workflow.
- Preserve backend, Strix, and frontend dependency security pins.
- Run repository tests, image builds, dependency review, SAST, and security scans on the exact head.

## References

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1: Recommendations for mitigating the
risk of software vulnerabilities* (NIST Special Publication 800-218).
https://doi.org/10.6028/NIST.SP.800-218

Open Container Initiative. (2025). *Open Container Initiative image format
specification*. https://specs.opencontainers.org/image-spec/

SLSA Community. (2025). *SLSA specification: Version 1.2*.
https://slsa.dev/spec/v1.2/

The in-toto Project. (n.d.). *in-toto technical specification*. Retrieved
August 5, 2026, from https://in-toto.io/docs/
''',
        encoding="utf-8",
    )

    operations = REPO_ROOT / "docs/operations/container-provenance-contract.md"
    operations_text = operations.read_text(encoding="utf-8")
    link = (
        "\n## Standards and evidence\n\n"
        "The rationale, threat model, verification boundary, and APA 7th "
        "references are maintained in "
        "[`docs/doctoring/container-provenance-contract.md`](../doctoring/container-provenance-contract.md).\n"
    )
    if link not in operations_text:
        operations.write_text(operations_text.rstrip() + link, encoding="utf-8")


def main() -> None:
    """Apply every bounded repair to the exact checked-out trigger commit."""
    update_base_image_pins()
    write_provenance_contract_tests()
    update_changelog()
    write_doctoring()


if __name__ == "__main__":
    main()
