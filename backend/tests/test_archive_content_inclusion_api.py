from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.archive_content_inclusion import (
    MAX_DISKSAGE_ARCHIVE_CONTENT_INCLUSION_BODY_BYTES,
)
from api.bounded_json import read_bounded_body
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    with TestClient(app, headers={"X-User-Id": "archive-proof-user"}) as test_client:
        yield test_client


def _inclusion_payload() -> dict[str, object]:
    return {
        "version": 1,
        "schema_kind": "disksage.archive-content-inclusion",
        "subset_archive": "/Downloads/smaller.zip",
        "superset_archive": "/Downloads/larger.zip",
        "root_mode": "keep-top-level",
        "subset_root_prefix": ".",
        "superset_root_prefix": ".",
        "subset_file_count": 106,
        "superset_file_count": 108,
        "subset_uncompressed_bytes": 220_149_200,
        "superset_uncompressed_bytes": 221_021_138,
        "matching_file_count": 106,
        "missing_file_count": 0,
        "changed_file_count": 0,
        "additional_file_count": 2,
        "subset_content_included": True,
        "archives_identical": False,
        "missing_paths": [],
        "changed_paths": [],
        "additional_paths": [
            "00_index/README_NotebookLM_v22_0.md",
            "02_core_source_documents/contract.pdf",
        ],
        "paths_truncated": False,
        "subset_manifest_sha256": (
            "ee827c74f099bb683501ef5b33ab990f7210eb43fbdf6ad8ce890a2918ce39c0"
        ),
        "superset_manifest_sha256": (
            "367f2cfd5f00a13a29db7a6ba8e1b050a654ded78553377af2acefb057121721"
        ),
        "comparison_fingerprint_sha256": (
            "7bcabfd62268f74d2b74f0d44cac700612ee3fb4d3de123d457a8eaaafd2810a"
        ),
    }


def test_validate_archive_content_inclusion_returns_redacted_acceptance(
    client: TestClient,
):
    response = client.post(
        "/api/archive-content-inclusion/validate", json=_inclusion_payload()
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "schema_version": 1,
        "schema_kind": "disksage.archive-content-inclusion",
    }
    assert "/Downloads/smaller.zip" not in response.text
    assert "contract.pdf" not in response.text
    assert "7bcabfd6" not in response.text


def test_validate_archive_content_inclusion_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/archive-content-inclusion/validate", json=_inclusion_payload()
        )

    assert response.status_code == 401


def test_validate_archive_content_inclusion_accepts_explicitly_truncated_samples(
    client: TestClient,
):
    payload = _inclusion_payload()
    payload["superset_file_count"] = 109
    payload["additional_file_count"] = 3
    payload["paths_truncated"] = True

    response = client.post("/api/archive-content-inclusion/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("matching_file_count", 105),
        lambda payload: payload.__setitem__("subset_content_included", False),
        lambda payload: payload.__setitem__("archives_identical", True),
        lambda payload: payload.__setitem__("version", True),
        lambda payload: payload.__setitem__("subset_manifest_sha256", "A" * 64),
        lambda payload: payload.__setitem__(
            "comparison_fingerprint_sha256", "0" * 64
        ),
        lambda payload: payload.update(
            {
                "superset_manifest_sha256": payload["subset_manifest_sha256"],
                "comparison_fingerprint_sha256": (
                    "42a7d0b1e87cc2242cdaaeafe66a0854cdfde5db06f8b40002cb096348192177"
                ),
            }
        ),
        lambda payload: payload.__setitem__("subset_archive", "/Downloads/larger.zip"),
        lambda payload: payload.__setitem__("subset_root_prefix", "wrapper"),
        lambda payload: payload["additional_paths"].reverse(),
        lambda payload: payload["additional_paths"].__setitem__(0, "../secret"),
        lambda payload: payload["additional_paths"].pop(),
        lambda payload: payload.__setitem__("paths_truncated", True),
        lambda payload: payload.__setitem__("unknown_field", "rejected"),
    ],
    ids=[
        "subset-count-mismatch",
        "inclusion-flag-mismatch",
        "identical-flag-mismatch",
        "boolean-version",
        "uppercase-digest",
        "fingerprint-mismatch",
        "equal-manifests-for-nonidentical-archives",
        "same-archive",
        "keep-top-level-prefix-mismatch",
        "unsorted-path-samples",
        "unsafe-path",
        "unreported-path-truncation",
        "invented-truncation",
        "unknown-field",
    ],
)
def test_validate_archive_content_inclusion_fails_closed(
    client: TestClient,
    mutate,
):
    payload = deepcopy(_inclusion_payload())
    mutate(payload)

    response = client.post("/api/archive-content-inclusion/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_archive_content_inclusion_invalid"}


def test_validate_archive_content_inclusion_accepts_stripped_distinct_wrappers(
    client: TestClient,
):
    payload = _inclusion_payload()
    payload["root_mode"] = "strip-shared-root"
    payload["subset_root_prefix"] = "smaller-root"
    payload["superset_root_prefix"] = "larger-root"
    payload["comparison_fingerprint_sha256"] = (
        "f9c923c3516292de07a1e487e18d0a4dc249e17bd2fdb35f1a5abf1396e1755e"
    )

    response = client.post("/api/archive-content-inclusion/validate", json=payload)

    assert response.status_code == 200


def test_validate_archive_content_inclusion_rejects_duplicate_json_keys(
    client: TestClient,
):
    raw = json.dumps(_inclusion_payload(), separators=(",", ":"))
    raw = raw.replace(
        '"matching_file_count":106', '"matching_file_count":0,"matching_file_count":106'
    )

    response = client.post(
        "/api/archive-content-inclusion/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_archive_content_inclusion_invalid"}


def test_validate_archive_content_inclusion_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/archive-content-inclusion/validate",
        content=b"{" + b" " * MAX_DISKSAGE_ARCHIVE_CONTENT_INCLUSION_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "disksage_archive_content_inclusion_too_large"}


class _OversizedChunk:
    def __len__(self) -> int:
        return MAX_DISKSAGE_ARCHIVE_CONTENT_INCLUSION_BODY_BYTES + 1

    def __iter__(self):
        raise AssertionError("oversized chunk must not be copied before rejection")


class _SingleChunkRequest:
    headers: dict[str, str] = {}

    async def stream(self):
        yield _OversizedChunk()


@pytest.mark.asyncio
async def test_read_bounded_body_rejects_oversized_chunk_before_copying():
    with pytest.raises(HTTPException) as exc_info:
        await read_bounded_body(
            _SingleChunkRequest(),
            max_body_bytes=MAX_DISKSAGE_ARCHIVE_CONTENT_INCLUSION_BODY_BYTES,
            too_large_error="too_large",
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "too_large"


def test_validate_archive_content_inclusion_has_no_database_dependency(
    client: TestClient,
):
    def fail_if_called():
        raise AssertionError(
            "archive content validation must not open a database session"
        )

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post(
            "/api/archive-content-inclusion/validate", json=_inclusion_payload()
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
