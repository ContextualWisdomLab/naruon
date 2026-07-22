from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import api.file_lineage as file_lineage_api
from api.file_lineage import MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    with TestClient(app, headers={"X-User-Id": "lineage-user"}) as test_client:
        yield test_client


def _lineage_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "schema_kind": "disksage.file-lineage",
        "source_kind": "file",
        "archive_kind": "document",
        "source_filename": "report.pdf",
        "source_relative_path": "reports/report.pdf",
        "source_context": "downloads",
        "raw_content_sha256": "d" * 64,
        "raw_content_blake3": "c" * 64,
        "bytes": 42,
        "production_time": {
            "selected_value_ms": 1_767_225_600_000,
            "selected_source": "embedded:exiftool:CreateDate",
            "confidence": "high",
            "evidence_precedence": [
                "embedded_metadata",
                "explicit_filename_date",
                "filesystem_created_at",
                "filesystem_modified_at",
            ],
        },
        "filesystem_time": {
            "created_at_ms": 1_767_225_600_000,
            "modified_at_ms": 1_767_229_200_000,
        },
        "metadata_evidence": [
            {
                "field": "production-date",
                "value": "2026-01-01",
                "source": "embedded:exiftool:CreateDate",
                "confidence": "high",
            }
        ],
        "content_title": "Report",
        "content_authors": ["Author"],
        "content_context": ["download-origin-host=example.com"],
        "duration_ms": None,
        "review": {
            "candidate_fingerprint": "b" * 64,
            "review_fingerprint": "f" * 64,
            "requires_review": True,
            "reason_codes": ["sensitive-document"],
            "decision_id": "decision-1",
            "disposition": "approved",
            "reviewed_at_ms": 1_767_229_300_000,
            "reviewed_by": "human:local:test",
            "rationale": "Embedded metadata checked",
        },
        "cloud_copy": {
            "receipt_id": "a" * 64,
            "lineage_fingerprint": "e" * 64,
            "provider": "onedrive",
            "destination_account_scope": "personal",
            "destination": "/cloud/report.pdf",
            "copied_at_ms": 1_767_229_400_000,
            "copy_verification_method": "copied-by-disk-sage",
            "local_copy_verified": True,
            "provider_write_executed": False,
            "provider_sync_confirmed": False,
            "sync_evidence_record_id": None,
            "sync_evidence_kind": None,
            "sync_evidence_id": None,
            "sync_confirmed_at_ms": None,
            "remote_object_id": None,
            "remote_revision": None,
            "remote_location_bound": None,
        },
    }


def test_validate_disksage_file_lineage_returns_redacted_acceptance(client: TestClient):
    response = client.post("/api/file-lineage/validate", json=_lineage_payload())

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "schema_version": 1,
        "schema_kind": "disksage.file-lineage",
    }
    assert "/cloud/report.pdf" not in response.text
    assert "decision-1" not in response.text
    assert "d" * 64 not in response.text


def test_validate_disksage_file_lineage_parses_strict_json_once(
    client: TestClient,
    monkeypatch,
):
    parse_calls = 0
    original_parse = file_lineage_api._parse_strict_json_body

    def counting_parse(body: bytes) -> object:
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(body)

    monkeypatch.setattr(
        file_lineage_api,
        "_parse_strict_json_body",
        counting_parse,
    )

    response = client.post("/api/file-lineage/validate", json=_lineage_payload())

    assert response.status_code == 200
    assert parse_calls == 1


@pytest.mark.parametrize("unsafe_character", ["\u200b", "\u202e", "\ue000", "\u0378"])
def test_validate_disksage_file_lineage_rejects_all_unicode_other_categories(
    client: TestClient,
    unsafe_character: str,
):
    payload = _lineage_payload()
    payload["source_context"] = f"downloads{unsafe_character}hidden"

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_file_lineage_invalid"}


def test_validate_disksage_file_lineage_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/file-lineage/validate", json=_lineage_payload()
        )

    assert response.status_code == 401


@pytest.mark.parametrize("source", ["filesystem:created", "filename:path-token"])
def test_validate_disksage_file_lineage_accepts_bound_production_sources(
    client: TestClient,
    source: str,
):
    payload = _lineage_payload()
    payload["production_time"]["selected_source"] = source
    if source == "filesystem:created":
        payload["production_time"]["selected_value_ms"] = payload["filesystem_time"][
            "created_at_ms"
        ]
    else:
        payload["production_time"]["confidence"] = "low"
        payload["metadata_evidence"] = [
            {
                "field": "filename-date-hint",
                "value": "2026-01-01",
                "source": source,
                "confidence": "low",
            }
        ]

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["production_time"].__setitem__(
            "evidence_precedence",
            [
                "explicit_filename_date",
                "embedded_metadata",
                "filesystem_created_at",
                "filesystem_modified_at",
            ],
        ),
        lambda payload: payload.__setitem__("source_filename", "other.pdf"),
        lambda payload: payload.__setitem__("source_relative_path", "../report.pdf"),
        lambda payload: payload.__setitem__("raw_content_sha256", "D" * 64),
        lambda payload: payload["cloud_copy"].__setitem__(
            "provider_write_executed", True
        ),
        lambda payload: payload["cloud_copy"].__setitem__("local_copy_verified", False),
        lambda payload: payload["cloud_copy"].__setitem__(
            "provider_sync_confirmed", True
        ),
        lambda payload: payload["review"].__setitem__("disposition", "held"),
        lambda payload: payload["production_time"].__setitem__(
            "unknown_field", "rejected"
        ),
        lambda payload: payload["production_time"].update(
            {
                "selected_source": "filesystem:created",
                "selected_value_ms": payload["filesystem_time"]["created_at_ms"] + 1,
            }
        ),
        lambda payload: payload["production_time"].__setitem__(
            "selected_source", "embedded:missing"
        ),
        lambda payload: payload["production_time"].__setitem__(
            "selected_source", "embedded:"
        ),
        lambda payload: payload["production_time"].__setitem__("confidence", "low"),
        lambda payload: payload["review"].__setitem__(
            "reviewed_at_ms", payload["cloud_copy"]["copied_at_ms"] + 1
        ),
        lambda payload: payload["cloud_copy"].update(
            {
                "sync_evidence_record_id": "9" * 64,
                "sync_evidence_kind": "provider-native-status",
                "sync_evidence_id": "file-provider:pending",
                "sync_confirmed_at_ms": payload["cloud_copy"]["copied_at_ms"] - 1,
            }
        ),
        lambda payload: payload["cloud_copy"].update(
            {
                "provider_sync_confirmed": True,
                "sync_evidence_record_id": "9" * 64,
                "sync_evidence_kind": "provider-api",
                "sync_evidence_id": "onedrive:item",
                "sync_confirmed_at_ms": payload["cloud_copy"]["copied_at_ms"] + 1,
                "remote_object_id": "remote-item-id",
                "remote_revision": "remote-revision",
                "remote_location_bound": False,
            }
        ),
        lambda payload: payload.__setitem__("source_context", "downloads\u0085next"),
        lambda payload: payload.__setitem__("unknown_field", "rejected"),
    ],
    ids=[
        "metadata-precedence-reordered",
        "source-filename-mismatch",
        "unsafe-relative-path",
        "uppercase-digest",
        "provider-write-invented",
        "local-copy-unverified",
        "sync-proof-incomplete",
        "review-not-approved",
        "unknown-nested-field",
        "filesystem-source-value-mismatch",
        "production-source-without-evidence",
        "empty-production-source-suffix",
        "production-source-confidence-mismatch",
        "review-after-copy",
        "sync-evidence-before-copy",
        "remote-location-unbound",
        "unicode-control-character",
        "unknown-field",
    ],
)
def test_validate_disksage_file_lineage_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_lineage_payload())
    mutate(payload)

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_file_lineage_invalid"}


@pytest.mark.parametrize(
    ("relative_path", "filename"),
    [
        ("reports/CON", "CON"),
        ("reports/con.txt", "con.txt"),
        ("reports/report.pdf.", "report.pdf."),
        ("reports/report.pdf ", "report.pdf "),
        ("reports/a:b", "a:b"),
    ],
)
def test_validate_disksage_file_lineage_rejects_nonportable_paths(
    client: TestClient,
    relative_path: str,
    filename: str,
):
    payload = _lineage_payload()
    payload["source_relative_path"] = relative_path
    payload["source_filename"] = filename

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_file_lineage_invalid"}


@pytest.mark.parametrize(
    "duplicate_fragment",
    [
        '"bytes":999,"bytes":42',
        '"selected_value_ms":0,"selected_value_ms":1767225600000',
    ],
    ids=["top-level", "nested"],
)
def test_validate_disksage_file_lineage_rejects_duplicate_json_keys(
    client: TestClient,
    duplicate_fragment: str,
):
    raw = json.dumps(_lineage_payload(), separators=(",", ":"))
    if duplicate_fragment.startswith('"bytes"'):
        raw = raw.replace('"bytes":42', duplicate_fragment, 1)
    else:
        raw = raw.replace('"selected_value_ms":1767225600000', duplicate_fragment, 1)

    response = client.post(
        "/api/file-lineage/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_file_lineage_invalid"}


def test_validate_disksage_file_lineage_rejects_excessive_json_nesting(
    client: TestClient,
):
    nested = '{"nested":' * 1_100 + "null" + "}" * 1_100

    response = client.post(
        "/api/file-lineage/validate",
        content=nested.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_file_lineage_invalid"}


def test_validate_disksage_file_lineage_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/file-lineage/validate",
        content=b"{" + b" " * MAX_DISKSAGE_FILE_LINEAGE_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "disksage_file_lineage_too_large"}


def test_validate_disksage_file_lineage_rejects_provider_capacity_assessment(
    client: TestClient,
):
    payload = _lineage_payload()
    payload["capacity"] = {
        "evidence_kind": "provider-api",
        "remaining_bytes": 1_000_000,
    }

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_file_lineage_invalid"}


def test_validate_disksage_file_lineage_accepts_incomplete_sync_evidence(
    client: TestClient,
):
    payload = _lineage_payload()
    payload["cloud_copy"].update(
        {
            "sync_evidence_record_id": "9" * 64,
            "sync_evidence_kind": "provider-native-status",
            "sync_evidence_id": "file-provider:pending",
            "sync_confirmed_at_ms": 1_767_229_500_000,
        }
    )

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 200
    assert response.json()["validation_scope"] == "schema-and-claim-consistency-only"


def test_validate_disksage_file_lineage_does_not_reflect_complete_sync_claim(
    client: TestClient,
):
    payload = _lineage_payload()
    payload["cloud_copy"].update(
        {
            "provider_sync_confirmed": True,
            "sync_evidence_record_id": "9" * 64,
            "sync_evidence_kind": "provider-api",
            "sync_evidence_id": "onedrive:item",
            "sync_confirmed_at_ms": 1_767_229_500_000,
            "remote_object_id": "remote-item-id",
            "remote_revision": "remote-revision",
            "remote_location_bound": True,
        }
    )

    response = client.post("/api/file-lineage/validate", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "schema_version": 1,
        "schema_kind": "disksage.file-lineage",
    }
    assert "remote-item-id" not in response.text
    assert "remote-revision" not in response.text


def test_validate_disksage_file_lineage_has_no_database_dependency(
    client: TestClient,
):
    def fail_if_called():
        raise AssertionError("file lineage validation must not open a database session")

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post("/api/file-lineage/validate", json=_lineage_payload())
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
