from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.cloud_capacity_assessment import (
    MAX_DISKSAGE_CLOUD_CAPACITY_BODY_BYTES,
)
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")

@pytest.fixture
def client():
    with TestClient(
        app,
        headers={"X-User-Id": "capacity-proof-user"},
    ) as test_client:
        yield test_client


def _icloud_payload() -> dict[str, object]:
    return {
        "schema_kind": "disksage.cloud-capacity-assessment",
        "schema_version": 1,
        "decision_batch_fingerprint_version": 1,
        "decision_batch_fingerprint": "d" * 64,
        "provider": "icloud",
        "destination_account_scope": "personal",
        "capacity": {
            "snapshot": {
                "schema_version": 3,
                "provider": "icloud",
                "account_scope": "personal",
                "evidence_kind": "provider-native-status",
                "observed_at_ms": 1_785_300_000_000,
                "total_bytes": None,
                "used_bytes": None,
                "remaining_bytes": 4_338_720_014_827,
                "trashed_bytes": None,
                "max_upload_size_bytes": None,
                "state": "available",
                "evidence_fingerprint": "e" * 64,
                "unavailable_reason": None,
            },
            "requested_bytes": 100,
            "largest_candidate_bytes": 0,
            "reserve_bytes": 10,
            "required_bytes": 110,
            "can_fit": True,
            "blockers": [],
            "notices": [],
        },
    }


def test_validate_cloud_capacity_returns_redacted_acceptance(client: TestClient):
    response = client.post(
        "/api/cloud-capacity-assessment/validate",
        json=_icloud_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "schema_version": 1,
        "schema_kind": "disksage.cloud-capacity-assessment",
        "capacity_schema_version": 3,
    }
    for submitted_value in [
        "icloud",
        "personal",
        "4338720014827",
        "d" * 64,
        "e" * 64,
    ]:
        assert submitted_value not in response.text


def test_validate_cloud_capacity_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/cloud-capacity-assessment/validate",
            json=_icloud_payload(),
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("schema_version", True),
        lambda payload: payload.__setitem__(
            "decision_batch_fingerprint_version", True
        ),
        lambda payload: payload.__setitem__("provider", "onedrive"),
        lambda payload: payload.__setitem__(
            "destination_account_scope", "organization"
        ),
        lambda payload: payload.__setitem__(
            "decision_batch_fingerprint", "D" * 64
        ),
        lambda payload: payload.__setitem__("unexpected", "rejected"),
        lambda payload: payload["capacity"]["snapshot"].__setitem__(
            "schema_version", True
        ),
        lambda payload: payload["capacity"]["snapshot"].__setitem__(
            "evidence_kind", "provider-api"
        ),
        lambda payload: payload["capacity"]["snapshot"].__setitem__(
            "total_bytes", 5_000_000_000_000
        ),
        lambda payload: payload["capacity"]["snapshot"].__setitem__(
            "state", "normal"
        ),
        lambda payload: payload["capacity"].__setitem__("required_bytes", 109),
        lambda payload: payload["capacity"].__setitem__("can_fit", False),
        lambda payload: payload["capacity"].__setitem__(
            "blockers", ["cloud-capacity-insufficient-with-reserve"]
        ),
        lambda payload: payload["capacity"].__setitem__(
            "notices", ["z-reason", "a-reason"]
        ),
        lambda payload: payload["capacity"]["snapshot"].__setitem__(
            "evidence_fingerprint", "E" * 64
        ),
        lambda payload: payload["capacity"]["snapshot"].__setitem__(
            "unavailable_reason", "secret provider response"
        ),
        lambda payload: payload["capacity"].__setitem__(
            "requested_bytes", 18_446_744_073_709_551_616
        ),
    ],
    ids=[
        "boolean-envelope-version",
        "boolean-batch-version",
        "envelope-provider-switch",
        "envelope-account-scope-switch",
        "uppercase-batch-fingerprint",
        "unknown-envelope-field",
        "boolean-capacity-version",
        "icloud-evidence-kind-switch",
        "icloud-invents-total",
        "icloud-state-mismatch",
        "required-byte-arithmetic",
        "fit-claim-mismatch",
        "blocker-claim-mismatch",
        "unsorted-notices",
        "uppercase-evidence-fingerprint",
        "unavailable-reason-on-evidence",
        "u64-overflow",
    ],
)
def test_validate_cloud_capacity_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_icloud_payload())
    mutate(payload)

    response = client.post(
        "/api/cloud-capacity-assessment/validate",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "disksage_cloud_capacity_assessment_invalid"
    }


def test_validate_cloud_capacity_accepts_unavailable_evidence(client: TestClient):
    payload = _icloud_payload()
    payload["capacity"] = {
        "snapshot": {
            "schema_version": 3,
            "provider": "icloud",
            "account_scope": None,
            "evidence_kind": "unavailable",
            "observed_at_ms": 1_785_300_000_000,
            "total_bytes": None,
            "used_bytes": None,
            "remaining_bytes": None,
            "trashed_bytes": None,
            "max_upload_size_bytes": None,
            "state": "unavailable",
            "evidence_fingerprint": None,
            "unavailable_reason": "icloud-native-quota-command-timeout",
        },
        "requested_bytes": 100,
        "largest_candidate_bytes": 0,
        "reserve_bytes": 10,
        "required_bytes": 110,
        "can_fit": None,
        "blockers": ["icloud-native-quota-command-timeout"],
        "notices": [],
    }

    response = client.post(
        "/api/cloud-capacity-assessment/validate",
        json=payload,
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {
            "schema_kind": "disksage.cloud-capacity-assessment",
            "schema_version": 1,
            "decision_batch_fingerprint_version": 1,
            "decision_batch_fingerprint": "a" * 64,
            "provider": "onedrive",
            "destination_account_scope": "organization",
            "capacity": {
                "snapshot": {
                    "schema_version": 3,
                    "provider": "onedrive",
                    "account_scope": "organization",
                    "evidence_kind": "provider-api",
                    "observed_at_ms": 1_785_300_000_000,
                    "total_bytes": 10_000,
                    "used_bytes": 6_000,
                    "remaining_bytes": 4_000,
                    "trashed_bytes": 5,
                    "max_upload_size_bytes": None,
                    "state": "normal",
                    "evidence_fingerprint": "b" * 64,
                    "unavailable_reason": None,
                },
                "requested_bytes": 2_000,
                "largest_candidate_bytes": 2_000,
                "reserve_bytes": 1_000,
                "required_bytes": 3_000,
                "can_fit": True,
                "blockers": [],
                "notices": [],
            },
        },
        {
            "schema_kind": "disksage.cloud-capacity-assessment",
            "schema_version": 1,
            "decision_batch_fingerprint_version": 1,
            "decision_batch_fingerprint": "c" * 64,
            "provider": "google-drive",
            "destination_account_scope": "unknown",
            "capacity": {
                "snapshot": {
                    "schema_version": 3,
                    "provider": "google-drive",
                    "account_scope": None,
                    "evidence_kind": "provider-api",
                    "observed_at_ms": 1_785_300_000_000,
                    "total_bytes": 10_000,
                    "used_bytes": 9_951,
                    "remaining_bytes": 49,
                    "trashed_bytes": 300,
                    "max_upload_size_bytes": 5_000,
                    "state": "critical",
                    "evidence_fingerprint": "f" * 64,
                    "unavailable_reason": None,
                },
                "requested_bytes": 10,
                "largest_candidate_bytes": 10,
                "reserve_bytes": 30,
                "required_bytes": 40,
                "can_fit": True,
                "blockers": [],
                "notices": [
                    "cloud-capacity-provider-state-critical",
                    "google-capacity-may-reflect-pooled-organization-storage",
                ],
            },
        },
        {
            "schema_kind": "disksage.cloud-capacity-assessment",
            "schema_version": 1,
            "decision_batch_fingerprint_version": 1,
            "decision_batch_fingerprint": "9" * 64,
            "provider": "google-drive",
            "destination_account_scope": "unknown",
            "capacity": {
                "snapshot": {
                    "schema_version": 3,
                    "provider": "google-drive",
                    "account_scope": None,
                    "evidence_kind": "provider-api",
                    "observed_at_ms": 1_785_300_000_000,
                    "total_bytes": None,
                    "used_bytes": 9_501,
                    "remaining_bytes": None,
                    "trashed_bytes": 300,
                    "max_upload_size_bytes": 5_000,
                    "state": "unlimited",
                    "evidence_fingerprint": "8" * 64,
                    "unavailable_reason": None,
                },
                "requested_bytes": 4_000,
                "largest_candidate_bytes": 4_000,
                "reserve_bytes": 1_000,
                "required_bytes": 5_000,
                "can_fit": True,
                "blockers": [],
                "notices": [
                    "cloud-capacity-provider-reports-unlimited",
                    "google-capacity-may-reflect-pooled-organization-storage",
                ],
            },
        },
    ],
    ids=["onedrive-organization", "google-limited", "google-unlimited"],
)
def test_validate_cloud_capacity_accepts_provider_specific_shapes(
    client: TestClient,
    payload: dict[str, object],
):
    response = client.post(
        "/api/cloud-capacity-assessment/validate",
        json=payload,
    )

    assert response.status_code == 200


def test_validate_cloud_capacity_rejects_duplicate_json_keys(client: TestClient):
    raw = json.dumps(_icloud_payload(), separators=(",", ":"))
    raw = raw.replace('"schema_version":1', '"schema_version":2,"schema_version":1', 1)

    response = client.post(
        "/api/cloud-capacity-assessment/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "disksage_cloud_capacity_assessment_invalid"
    }


def test_validate_cloud_capacity_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/cloud-capacity-assessment/validate",
        content=b"{" + b" " * MAX_DISKSAGE_CLOUD_CAPACITY_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "disksage_cloud_capacity_assessment_too_large"
    }


def test_validate_cloud_capacity_has_no_database_dependency(client: TestClient):
    def fail_if_called():
        raise AssertionError("capacity validation must not open a database session")

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post(
            "/api/cloud-capacity-assessment/validate",
            json=_icloud_payload(),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
