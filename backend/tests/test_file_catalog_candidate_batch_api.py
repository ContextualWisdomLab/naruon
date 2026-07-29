from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.file_catalog_candidate_batch import (
    MAX_DISKSAGE_FILE_CATALOG_BODY_BYTES,
)
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")

EMBEDDED_MS = 1_766_966_400_000
FILENAME_MS = 1_767_052_800_000
CREATED_MS = 1_767_225_600_000
MODIFIED_MS = 1_767_312_000_000


@pytest.fixture
def client():
    with TestClient(
        app,
        headers={"X-User-Id": "catalog-contract-user"},
    ) as test_client:
        yield test_client


def _evidence(
    field: str,
    value: str,
    source: str,
    confidence: str,
) -> dict[str, object]:
    return {
        "field": field,
        "value": value,
        "source": source,
        "confidence": confidence,
    }


def _payload(
    source_class: str = "embedded_metadata",
) -> dict[str, object]:
    source_shapes = {
        "embedded_metadata": (
            EMBEDDED_MS,
            "embedded:ooxml:created",
            "high",
            [
                _evidence(
                    "production-date",
                    "2025-12-29",
                    "embedded:ooxml:created",
                    "high",
                ),
                _evidence(
                    "filename-date-hint",
                    "2025-12-30",
                    "filename:path-token",
                    "low",
                ),
                _evidence(
                    "filesystem-created-date",
                    "2026-01-01",
                    "filesystem:created",
                    "low",
                ),
                _evidence(
                    "filesystem-modified-date",
                    "2026-01-02",
                    "filesystem:modified",
                    "low",
                ),
            ],
        ),
        "explicit_filename_date": (
            FILENAME_MS,
            "filename:path-token",
            "low",
            [
                _evidence(
                    "filename-date-hint",
                    "2025-12-30",
                    "filename:path-token",
                    "low",
                ),
                _evidence(
                    "filesystem-created-date",
                    "2026-01-01",
                    "filesystem:created",
                    "low",
                ),
                _evidence(
                    "filesystem-modified-date",
                    "2026-01-02",
                    "filesystem:modified",
                    "low",
                ),
            ],
        ),
        "filesystem_created": (
            CREATED_MS,
            "filesystem:created",
            "low",
            [
                _evidence(
                    "filesystem-created-date",
                    "2026-01-01",
                    "filesystem:created",
                    "low",
                ),
                _evidence(
                    "filesystem-modified-date",
                    "2026-01-02",
                    "filesystem:modified",
                    "low",
                ),
            ],
        ),
        "filesystem_modified": (
            MODIFIED_MS,
            "filesystem:modified-fallback",
            "low",
            [
                _evidence(
                    "filesystem-modified-date",
                    "2026-01-02",
                    "filesystem:modified",
                    "low",
                ),
            ],
        ),
    }
    production_ms, source, confidence, metadata_evidence = source_shapes[source_class]
    metadata_evidence.append(
        _evidence(
            "private-context-tag",
            "private-project-codename",
            "embedded:ooxml:subject",
            "medium",
        )
    )
    return {
        "schema": "disksage.file-catalog-candidate-batch",
        "version": 1,
        "production_time_precedence": [
            "embedded_metadata",
            "explicit_filename_date",
            "filesystem_created",
            "filesystem_modified",
        ],
        "generated_at_ms": 1_767_400_000_000,
        "candidates": [
            {
                "candidate_fingerprint": "a" * 64,
                "review_fingerprint": "b" * 64,
                "destination_provider": "icloud",
                "destination_account_scope": "personal",
                "archive_kind": "document",
                "bytes": 4096,
                "created_ms": CREATED_MS,
                "modified_ms": MODIFIED_MS,
                "production_time_ms": production_ms,
                "production_time_source": source,
                "production_time_confidence": confidence,
                "requires_review": True,
                "review_reasons": ["private-review-reason"],
                "content_title": "private-title",
                "content_authors": ["private-author"],
                "content_context": ["private-content-context"],
                "duration_ms": None,
                "dataset_profile": {
                    "format": "xlsx",
                    "sampled_rows": 12,
                    "sampled_worksheets": 1,
                    "worksheet_names": ["private-worksheet"],
                    "profile_complete": True,
                    "sample_truncated": False,
                    "columns": [
                        {
                            "name": "private-column",
                            "inferred_type": "string",
                            "observed_values": 12,
                            "missing_values": 0,
                            "sensitive_name": True,
                        }
                    ],
                    "quality_warnings": ["private-quality-warning"],
                },
                "metadata_evidence": metadata_evidence,
                "blocked_reason": None,
            }
        ],
    }


@pytest.mark.parametrize(
    "source_class",
    [
        "embedded_metadata",
        "explicit_filename_date",
        "filesystem_created",
        "filesystem_modified",
    ],
)
def test_validate_catalog_accepts_all_precedence_sources(
    client: TestClient,
    source_class: str,
):
    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        json=_payload(source_class),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-metadata-precedence-and-claim-consistency-only",
        "schema_kind": "disksage.file-catalog-candidate-batch",
        "schema_version": 1,
        "candidate_count": 1,
        "private_content_reflected": False,
        "persisted": False,
        "llm_used": False,
        "copy_authorized": False,
        "eviction_authorized": False,
        "persistable_as_file_asset": False,
        "content_sha256_required": True,
        "semantic_projection_delegated_to": "semantic-data-portal",
    }
    for private_value in [
        "private-project-codename",
        "private-review-reason",
        "private-title",
        "private-author",
        "private-content-context",
        "private-worksheet",
        "private-column",
        "private-quality-warning",
        "a" * 64,
        "b" * 64,
    ]:
        assert private_value not in response.text


def test_validate_catalog_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/file-catalog-candidate-batch/validate",
            json=_payload(),
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("version", True),
        lambda payload: payload.__setitem__("schema", "unknown"),
        lambda payload: payload.__setitem__(
            "production_time_precedence",
            [
                "explicit_filename_date",
                "embedded_metadata",
                "filesystem_created",
                "filesystem_modified",
            ],
        ),
        lambda payload: payload.__setitem__("unexpected", "rejected"),
        lambda payload: payload["candidates"][0].__setitem__("bytes", True),
        lambda payload: payload["candidates"][0].__setitem__(
            "candidate_fingerprint", "A" * 64
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "production_time_source", "filename:guess"
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "production_time_ms", FILENAME_MS
        ),
        lambda payload: payload["candidates"][0].__setitem__("requires_review", False),
        lambda payload: payload["candidates"][0].__setitem__(
            "production_time_confidence", "certain"
        ),
    ],
    ids=[
        "boolean-version",
        "unknown-schema",
        "precedence-reordered",
        "unknown-envelope-field",
        "boolean-bytes",
        "uppercase-fingerprint",
        "unsupported-time-source",
        "selected-date-does-not-match-evidence",
        "review-claim-mismatch",
        "unknown-confidence",
    ],
)
def test_validate_catalog_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_payload())
    mutate(payload)

    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "disksage_file_catalog_candidate_batch_invalid"
    }


def test_validate_catalog_rejects_lower_precedence_with_higher_evidence(
    client: TestClient,
):
    payload = _payload("explicit_filename_date")
    payload["candidates"][0]["metadata_evidence"].append(
        _evidence(
            "production-date",
            "2025-12-29",
            "embedded:ooxml:created",
            "high",
        )
    )

    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        json=payload,
    )

    assert response.status_code == 422


def test_validate_catalog_requires_low_confidence_for_non_embedded_source(
    client: TestClient,
):
    payload = _payload("filesystem_created")
    payload["candidates"][0]["production_time_confidence"] = "medium"

    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        json=payload,
    )

    assert response.status_code == 422


def test_validate_catalog_rejects_duplicate_candidate_fingerprints(
    client: TestClient,
):
    payload = _payload()
    duplicate = deepcopy(payload["candidates"][0])
    duplicate["review_fingerprint"] = "c" * 64
    payload["candidates"].append(duplicate)

    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "private_coordinate_field",
    [
        "src",
        "dst",
        "filename",
        "relative_path",
        "account_id",
        "object_id",
        "locator",
    ],
)
def test_validate_catalog_rejects_storage_coordinates_and_identifiers(
    client: TestClient,
    private_coordinate_field: str,
):
    payload = _payload()
    payload["candidates"][0][private_coordinate_field] = "private-coordinate"

    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        json=payload,
    )

    assert response.status_code == 422


def test_validate_catalog_rejects_duplicate_json_keys(client: TestClient):
    raw = json.dumps(_payload(), separators=(",", ":"))
    raw = raw.replace('"version":1', '"version":2,"version":1', 1)

    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "disksage_file_catalog_candidate_batch_invalid"
    }


def test_validate_catalog_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/file-catalog-candidate-batch/validate",
        content=b"{" + b" " * MAX_DISKSAGE_FILE_CATALOG_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "disksage_file_catalog_candidate_batch_too_large"
    }


def test_validate_catalog_has_no_database_dependency(client: TestClient):
    def fail_if_called():
        raise AssertionError("catalog validation must not open a database session")

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post(
            "/api/file-catalog-candidate-batch/validate",
            json=_payload(),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
