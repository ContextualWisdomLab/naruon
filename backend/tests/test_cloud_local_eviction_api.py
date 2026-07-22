from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.cloud_local_eviction import (
    MAX_DISKSAGE_CLOUD_LOCAL_EVICTION_BODY_BYTES,
)
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    with TestClient(app, headers={"X-User-Id": "eviction-proof-user"}) as test_client:
        yield test_client


def _plan() -> dict[str, object]:
    root = "/Users/example/Library/Mobile Documents/com~apple~CloudDocs"
    return {
        "version": 1,
        "provider": "icloud",
        "account_scope": "unknown",
        "cloud_root": root,
        "path": f"{root}/Archive/report.wav",
        "logical_bytes": 4_000,
        "allocated_bytes": 4_096,
        "filesystem_modified_ms": 10,
        "observed_at_ms": 100,
        "icloud_state": {
            "is_ubiquitous": True,
            "is_uploaded": True,
            "is_uploading": False,
            "is_downloading": False,
            "downloading_status_current": True,
            "has_unresolved_conflicts": False,
            "is_excluded_from_sync": False,
        },
        "active_use": {
            "method": "lsof-fp+ps-command",
            "evidence_complete": True,
            "active": False,
            "observed_pids": [],
            "results_truncated": False,
            "error": None,
        },
        "plan_fingerprint": "a" * 64,
        "eligible_after_human_approval": True,
        "blockers": ["human-local-eviction-approval-required"],
        "notices": [
            "file-content-not-opened",
            "embedded-metadata-not-required-for-local-cache-eviction",
            "cloud-object-must-remain-present",
            "allocated-byte-reduction-is-not-volume-free-space-proof",
        ],
    }


def _plan_output() -> dict[str, object]:
    return {
        "action": "plan-icloud-local-eviction",
        "mutation_executed": False,
        "plan": _plan(),
    }


def _execution_output() -> dict[str, object]:
    approval_id = "b" * 64
    result_id = "c" * 64
    return {
        "action": "evict-icloud-local-copy",
        "mutation_executed": True,
        "plan": _plan(),
        "approval": {
            "version": 1,
            "approval_id": approval_id,
            "plan_fingerprint": "a" * 64,
            "approved_at_ms": 101,
            "approved_by": "human:test-operator",
            "rationale": "Retain the iCloud object and release only local allocation.",
        },
        "approval_record": (f"/Users/example/evidence/{approval_id}.approval.json"),
        "result": {
            "version": 1,
            "result_id": result_id,
            "plan_fingerprint": "a" * 64,
            "approval_id": approval_id,
            "path": _plan()["path"],
            "requested_at_ms": 102,
            "allocated_bytes_before": 4_096,
            "allocated_bytes_after": 0,
            "observed_allocation_reduction_bytes": 4_096,
            "eviction_request_succeeded": True,
            "cloud_item_path_retained": True,
            "is_ubiquitous_after": True,
            "local_allocation_reduction_verified": True,
            "verification_complete": True,
            "verification_blockers": [],
            "notices": [
                "cloud-object-delete-not-requested",
                "observed-allocation-reduction-is-not-volume-free-space-proof",
            ],
        },
        "result_record": f"/Users/example/evidence/{result_id}.result.json",
    }


def test_validate_plan_returns_redacted_acceptance(client: TestClient):
    payload = _plan_output()

    response = client.post("/api/cloud-local-eviction/validate", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "version": 1,
        "evidence_kind": "disksage.icloud-local-eviction",
        "evidence_stage": "plan",
    }
    assert "report.wav" not in response.text
    assert "4096" not in response.text
    assert "test-operator" not in response.text


def test_validate_execution_returns_redacted_acceptance(client: TestClient):
    payload = _execution_output()

    response = client.post("/api/cloud-local-eviction/validate", json=payload)

    assert response.status_code == 200
    assert response.json()["evidence_stage"] == "execution"
    assert payload["approval"]["approval_id"] not in response.text
    assert payload["result"]["result_id"] not in response.text


def test_validate_plan_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/cloud-local-eviction/validate",
            json=_plan_output(),
        )

    assert response.status_code == 401


def test_validate_fail_closed_blocked_plan(client: TestClient):
    payload = _plan_output()
    plan = payload["plan"]
    plan["icloud_state"]["is_uploaded"] = False
    plan["icloud_state"]["is_uploading"] = True
    plan["active_use"].update(
        {
            "active": True,
            "observed_pids": [42],
        }
    )
    plan["eligible_after_human_approval"] = False
    plan["blockers"] = [
        "icloud-upload-not-confirmed",
        "icloud-upload-still-running",
        "active-file-use-detected",
        "human-local-eviction-approval-required",
    ]

    response = client.post("/api/cloud-local-eviction/validate", json=payload)

    assert response.status_code == 200


def test_validate_execution_accepts_incomplete_post_request_verification(
    client: TestClient,
):
    payload = _execution_output()
    payload["result"].update(
        {
            "allocated_bytes_after": 4_096,
            "observed_allocation_reduction_bytes": 0,
            "local_allocation_reduction_verified": False,
            "verification_complete": False,
            "verification_blockers": ["local-allocation-reduction-unverified"],
        }
    )

    response = client.post("/api/cloud-local-eviction/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["plan"].__setitem__("version", True),
        lambda payload: payload.__setitem__("unknown", "rejected"),
        lambda payload: payload.__setitem__("mutation_executed", True),
        lambda payload: payload["plan"].__setitem__("provider", "onedrive"),
        lambda payload: payload["plan"].__setitem__(
            "path", "/Users/example/outside.wav"
        ),
        lambda payload: payload["plan"].__setitem__(
            "path", "/Users/example/Cloud/../escape.wav"
        ),
        lambda payload: payload["plan"].__setitem__("allocated_bytes", True),
        lambda payload: payload["plan"].__setitem__("plan_fingerprint", "A" * 64),
        lambda payload: payload["plan"]["notices"].pop(),
        lambda payload: payload["plan"]["active_use"].__setitem__(
            "observed_pids", [42, 41]
        ),
        lambda payload: payload["plan"]["active_use"].__setitem__("active", True),
        lambda payload: payload["plan"]["active_use"].__setitem__(
            "evidence_complete", False
        ),
        lambda payload: payload["plan"].__setitem__("blockers", []),
        lambda payload: payload["plan"]["icloud_state"].__setitem__(
            "is_uploaded", False
        ),
        lambda payload: payload["plan"].__setitem__(
            "eligible_after_human_approval", False
        ),
    ],
    ids=[
        "boolean-version",
        "unknown-field",
        "mutation-claim",
        "provider",
        "outside-root",
        "parent-component",
        "boolean-allocation",
        "uppercase-fingerprint",
        "missing-notice",
        "unsorted-pids",
        "active-pid-mismatch",
        "completeness-mismatch",
        "missing-human-blocker",
        "state-blocker-mismatch",
        "eligibility-mismatch",
    ],
)
def test_validate_plan_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_plan_output())
    mutate(payload)

    response = client.post("/api/cloud-local-eviction/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_eviction_invalid"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["approval"].__setitem__("plan_fingerprint", "d" * 64),
        lambda payload: payload["approval"].__setitem__("approved_by", "agent:test"),
        lambda payload: payload["approval"].__setitem__("approved_at_ms", 99),
        lambda payload: payload["result"].__setitem__("plan_fingerprint", "d" * 64),
        lambda payload: payload["result"].__setitem__("approval_id", "d" * 64),
        lambda payload: payload["result"].__setitem__(
            "path", "/Users/example/other.wav"
        ),
        lambda payload: payload["result"].__setitem__("allocated_bytes_before", 8_192),
        lambda payload: payload["result"].__setitem__("requested_at_ms", 100),
        lambda payload: payload["result"].__setitem__(
            "observed_allocation_reduction_bytes", 1
        ),
        lambda payload: payload["result"].__setitem__(
            "local_allocation_reduction_verified", False
        ),
        lambda payload: payload["result"].__setitem__("verification_complete", False),
        lambda payload: payload.__setitem__(
            "approval_record",
            "/Users/example/Library/Mobile Documents/com~apple~CloudDocs/records/a.json",
        ),
        lambda payload: payload.__setitem__(
            "result_record", "/Users/example/evidence/wrong.result.json"
        ),
        lambda payload: payload.__setitem__(
            "result_record", payload["approval_record"]
        ),
    ],
    ids=[
        "approval-plan-binding",
        "non-human-approval",
        "approval-time-order",
        "result-plan-binding",
        "result-approval-binding",
        "result-path-binding",
        "before-allocation-binding",
        "request-time-order",
        "reduction-claim",
        "reduction-verification",
        "verification-completeness",
        "record-inside-cloud",
        "result-record-name",
        "record-alias",
    ],
)
def test_validate_execution_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_execution_output())
    mutate(payload)

    response = client.post("/api/cloud-local-eviction/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_eviction_invalid"}


def test_validate_rejects_duplicate_json_keys(client: TestClient):
    raw = json.dumps(_plan_output(), separators=(",", ":"))
    raw = raw.replace(
        '"mutation_executed":false',
        '"mutation_executed":true,"mutation_executed":false',
    )

    response = client.post(
        "/api/cloud-local-eviction/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_eviction_invalid"}


def test_validate_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/cloud-local-eviction/validate",
        content=b"{" + b" " * MAX_DISKSAGE_CLOUD_LOCAL_EVICTION_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "disksage_cloud_local_eviction_too_large"}


def test_validate_has_no_database_dependency(client: TestClient):
    def fail_if_called():
        raise AssertionError("eviction validation must not open a database session")

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post(
            "/api/cloud-local-eviction/validate",
            json=_execution_output(),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
