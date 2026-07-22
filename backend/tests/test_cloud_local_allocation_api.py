from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.cloud_local_allocation import (
    MAX_DISKSAGE_CLOUD_LOCAL_ALLOCATION_BODY_BYTES,
)
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    with TestClient(app, headers={"X-User-Id": "allocation-proof-user"}) as test_client:
        yield test_client


def _base_notices() -> list[str]:
    return [
        "metadata-only-content-not-opened",
        "embedded-production-metadata-not-inspected",
        "provider-sync-not-attested",
        "inventory-does-not-authorize-eviction",
    ]


def _candidate(path: str) -> dict[str, object]:
    return {
        "path": path,
        "logical_bytes": 8_000,
        "allocated_bytes": 8_192,
        "filesystem_created_ms": 1_784_206_251_857,
        "filesystem_modified_ms": 1_784_216_980_830,
        "allocation_evidence": "filesystem:st-blocks-512",
        "content_opened": False,
        "embedded_metadata_inspected": False,
        "provider_sync_attested": False,
        "eviction_blockers": [
            "provider-sync-unverified",
            "human-eviction-approval-required",
        ],
    }


def _inventory_payload() -> dict[str, object]:
    root = "/Users/example/Library/Mobile Documents/com~apple~CloudDocs/Archive"
    return {
        "version": 1,
        "cloud_root_id": f"{root}#evidence",
        "provider": "icloud",
        "account_scope": "unknown",
        "cloud_root": root,
        "observed_at_ms": 1_784_611_083_134,
        "options": {
            "min_allocated_bytes": 4_096,
            "max_entries": 50_000,
            "max_results": 20,
            "max_depth": 4,
            "max_duration_ms": 30_000,
        },
        "visited_entries": 9,
        "visited_files": 2,
        "visited_directories": 7,
        "skipped_entries": 0,
        "allocated_candidate_bytes": 8_192,
        "candidates": [_candidate(f"{root}/report.pdf")],
        "results_truncated": False,
        "evidence_complete": True,
        "stop_reasons": [],
        "notices": _base_notices(),
    }


def _hard_timeout_payload() -> dict[str, object]:
    payload = _inventory_payload()
    payload.update(
        {
            "visited_entries": 0,
            "visited_files": 0,
            "visited_directories": 0,
            "skipped_entries": 0,
            "allocated_candidate_bytes": 0,
            "candidates": [],
            "results_truncated": False,
            "evidence_complete": False,
            "stop_reasons": ["hard-timeout-reached"],
            "notices": _base_notices()
            + ["inventory-incomplete", "worker-hard-timeout"],
        }
    )
    return payload


def _inventory_v2_payload() -> dict[str, object]:
    payload = deepcopy(_inventory_payload())
    payload["version"] = 2
    payload["options"]["max_issues"] = 10
    payload["issues"] = []
    payload["issues_truncated"] = False
    return payload


def _v2_issue_payload() -> dict[str, object]:
    payload = _inventory_v2_payload()
    payload.update(
        {
            "visited_entries": 4,
            "visited_files": 1,
            "visited_directories": 1,
            "skipped_entries": 2,
            "allocated_candidate_bytes": 0,
            "candidates": [],
            "issues": [
                {
                    "relative_scope": "Projects/Search",
                    "kind": "read-entry-failed",
                    "reason": "timed-out",
                },
                {
                    "relative_scope": "Projects/reference.drawio",
                    "kind": "symlink-skipped",
                    "reason": "policy-not-followed",
                },
            ],
            "evidence_complete": False,
            "stop_reasons": ["entry-errors"],
            "notices": _base_notices() + ["inventory-incomplete"],
        }
    )
    return payload


def test_validate_inventory_returns_redacted_acceptance(client: TestClient):
    payload = _inventory_payload()

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "version": 1,
        "evidence_kind": "disksage.cloud-local-allocation-inventory",
    }
    assert payload["cloud_root"] not in response.text
    assert "report.pdf" not in response.text
    assert "8192" not in response.text


def test_validate_inventory_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/cloud-local-allocation/validate",
            json=_inventory_payload(),
        )

    assert response.status_code == 401


def test_validate_inventory_accepts_fail_closed_hard_timeout(client: TestClient):
    response = client.post(
        "/api/cloud-local-allocation/validate",
        json=_hard_timeout_payload(),
    )

    assert response.status_code == 200


def test_validate_inventory_accepts_v2_bounded_issue_evidence(client: TestClient):
    payload = _v2_issue_payload()

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert "Projects/Search" not in response.text
    assert "timed-out" not in response.text


def test_validate_inventory_accepts_v2_truncated_issue_evidence(
    client: TestClient,
):
    payload = _v2_issue_payload()
    payload["options"]["max_issues"] = 1
    payload["issues"] = payload["issues"][:1]
    payload["issues_truncated"] = True
    payload["notices"].append("inventory-issues-truncated")

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "stop_reason",
    ["entry-errors", "allocated-byte-evidence-unavailable"],
)
def test_validate_inventory_accepts_v2_stop_evidence_hidden_by_issue_truncation(
    client: TestClient,
    stop_reason: str,
):
    payload = _v2_issue_payload()
    payload["options"]["max_issues"] = 1
    payload["issues"] = payload["issues"][1:]
    payload["issues_truncated"] = True
    payload["stop_reasons"] = [stop_reason]
    payload["notices"].append("inventory-issues-truncated")

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200


def test_validate_inventory_accepts_v2_fail_closed_hard_timeout(
    client: TestClient,
):
    payload = _hard_timeout_payload()
    payload["version"] = 2
    payload["options"]["max_issues"] = 10
    payload["issues"] = []
    payload["issues_truncated"] = False

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["options"].pop("max_issues"),
        lambda payload: payload.pop("issues"),
        lambda payload: payload.pop("issues_truncated"),
        lambda payload: payload["issues"][0].__setitem__(
            "relative_scope", "/absolute/path"
        ),
        lambda payload: payload["issues"][0].__setitem__(
            "relative_scope", "Projects/../escape"
        ),
        lambda payload: payload["issues"][0].__setitem__(
            "reason", "policy-not-followed"
        ),
        lambda payload: payload.__setitem__("skipped_entries", 3),
        lambda payload: payload.__setitem__("stop_reasons", []),
        lambda payload: payload["notices"].append("inventory-issues-truncated"),
        lambda payload: payload["options"].__setitem__("max_issues", 1_001),
    ],
    ids=[
        "missing-issue-bound",
        "missing-issues",
        "missing-truncation-flag",
        "absolute-issue-scope",
        "parent-issue-scope",
        "kind-reason-mismatch",
        "skip-accounting-mismatch",
        "entry-stop-mismatch",
        "notice-mismatch",
        "issue-bound-overflow",
    ],
)
def test_validate_inventory_v2_issues_fail_closed(client: TestClient, mutate):
    payload = deepcopy(_v2_issue_payload())
    mutate(payload)

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_rejects_v2_fields_on_version_1(client: TestClient):
    payload = _inventory_payload()
    payload["options"]["max_issues"] = 10
    payload["issues"] = []
    payload["issues_truncated"] = False

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_accepts_bounded_empty_and_truncated_reports(
    client: TestClient,
):
    empty = _inventory_payload()
    empty.update(
        {
            "provider": "google-drive",
            "account_scope": "personal",
            "visited_entries": 3,
            "visited_files": 3,
            "visited_directories": 0,
            "allocated_candidate_bytes": 0,
            "candidates": [],
        }
    )
    assert (
        client.post("/api/cloud-local-allocation/validate", json=empty).status_code
        == 200
    )

    truncated = _inventory_payload()
    truncated["options"]["max_results"] = 1
    truncated["allocated_candidate_bytes"] = 16_384
    truncated["results_truncated"] = True
    truncated["notices"] = _base_notices() + ["candidate-output-truncated"]
    assert (
        client.post(
            "/api/cloud-local-allocation/validate",
            json=truncated,
        ).status_code
        == 200
    )


def test_validate_inventory_accepts_skipped_symlink_as_incomplete(
    client: TestClient,
):
    payload = _inventory_payload()
    payload.update(
        {
            "visited_entries": 1,
            "visited_files": 0,
            "visited_directories": 0,
            "skipped_entries": 1,
            "allocated_candidate_bytes": 0,
            "candidates": [],
            "evidence_complete": False,
            "notices": _base_notices() + ["inventory-incomplete"],
        }
    )

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200


def test_validate_inventory_accepts_rust_saturating_allocation_total(
    client: TestClient,
):
    payload = _inventory_payload()
    second = _candidate(f"{payload['cloud_root']}/second.bin")
    payload["candidates"].append(second)
    for candidate in payload["candidates"]:
        candidate["allocated_bytes"] = 18_446_744_073_709_551_615
    payload["allocated_candidate_bytes"] = 18_446_744_073_709_551_615

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("version", True),
        lambda payload: payload.__setitem__("unknown_field", "rejected"),
        lambda payload: payload["options"].__setitem__("max_entries", 0),
        lambda payload: payload["options"].__setitem__("max_results", 10_001),
        lambda payload: payload["options"].__setitem__("max_duration_ms", 300_001),
        lambda payload: payload.__setitem__("visited_entries", True),
        lambda payload: payload.__setitem__("visited_entries", 8),
        lambda payload: payload["candidates"][0].__setitem__("content_opened", True),
        lambda payload: payload["candidates"][0].__setitem__(
            "embedded_metadata_inspected", True
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "provider_sync_attested", True
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "allocation_evidence", "logical-size"
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "eviction_blockers", ["provider-sync-unverified"]
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "path", "/Users/example/outside.pdf"
        ),
        lambda payload: payload["candidates"][0].__setitem__(
            "path", "/Users/example/Archive/../escape.pdf"
        ),
        lambda payload: payload["candidates"][0].__setitem__("allocated_bytes", 1),
        lambda payload: payload.__setitem__("allocated_candidate_bytes", 8_191),
        lambda payload: payload.__setitem__("allocated_candidate_bytes", 8_193),
        lambda payload: payload.__setitem__("evidence_complete", False),
        lambda payload: payload["notices"].pop(),
        lambda payload: payload["stop_reasons"].append("unknown-stop"),
        lambda payload: payload["candidates"][0].__setitem__(
            "logical_bytes", 18_446_744_073_709_551_616
        ),
    ],
    ids=[
        "boolean-version",
        "unknown-field",
        "zero-entry-bound",
        "result-bound-overflow",
        "duration-bound-overflow",
        "boolean-counter",
        "counter-mismatch",
        "content-opened",
        "embedded-metadata-invented",
        "provider-sync-invented",
        "unsupported-allocation-evidence",
        "missing-eviction-blocker",
        "candidate-outside-root",
        "candidate-parent-component",
        "candidate-below-threshold",
        "visible-total-too-small",
        "complete-total-mismatch",
        "completeness-contradiction",
        "notice-contradiction",
        "unknown-stop-reason",
        "u64-overflow",
    ],
)
def test_validate_inventory_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_inventory_payload())
    mutate(payload)

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_rejects_duplicate_candidates(client: TestClient):
    payload = _inventory_payload()
    payload["visited_files"] = 3
    payload["visited_entries"] = 10
    payload["candidates"].append(deepcopy(payload["candidates"][0]))
    payload["allocated_candidate_bytes"] = 16_384

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_rejects_case_aliases_on_windows(client: TestClient):
    payload = _inventory_payload()
    payload["cloud_root"] = "C:\\Cloud"
    payload["candidates"] = [
        _candidate("C:\\Cloud\\File.bin"),
        _candidate("c:\\cloud\\file.BIN"),
    ]
    payload["visited_files"] = 3
    payload["visited_entries"] = 10
    payload["allocated_candidate_bytes"] = 16_384

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_rejects_nonempty_hard_timeout(client: TestClient):
    payload = _hard_timeout_payload()
    payload["visited_entries"] = 1

    response = client.post("/api/cloud-local-allocation/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_rejects_duplicate_json_keys(client: TestClient):
    raw = json.dumps(_inventory_payload(), separators=(",", ":"))
    raw = raw.replace('"version":1', '"version":2,"version":1')

    response = client.post(
        "/api/cloud-local-allocation/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_local_allocation_invalid"}


def test_validate_inventory_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/cloud-local-allocation/validate",
        content=b"{" + b" " * MAX_DISKSAGE_CLOUD_LOCAL_ALLOCATION_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "disksage_cloud_local_allocation_too_large"}


def test_validate_inventory_has_no_database_dependency(client: TestClient):
    def fail_if_called():
        raise AssertionError("allocation validation must not open a database session")

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post(
            "/api/cloud-local-allocation/validate",
            json=_inventory_payload(),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
