from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.reclaim_plan import MAX_DISKSAGE_RECLAIM_PLAN_BODY_BYTES
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    with TestClient(app, headers={"X-User-Id": "reclaim-proof-user"}) as test_client:
        yield test_client


def _reason_codes(*, operation: str, allocation_available: bool = True) -> list[str]:
    codes = [
        "physical-reclaimability-unverified",
        "shared-extents-or-clones-unproven",
        (
            "allocated-bytes-are-not-reclaimability-proof"
            if allocation_available
            else "allocated-size-unavailable"
        ),
    ]
    if operation == "trash":
        codes.append("trash-retains-bytes-until-emptied")
    return codes


def _estimate(
    logical_bytes: int,
    allocated_bytes: int | None,
    *,
    operation: str,
) -> dict[str, object]:
    return {
        "logical_bytes": logical_bytes,
        "allocated_bytes": allocated_bytes,
        "physically_reclaimable_bytes": None,
        "status": "unverified",
        "reason_codes": _reason_codes(
            operation=operation,
            allocation_available=allocated_bytes is not None,
        ),
    }


def _reclaim_payload(*, operation: str = "trash") -> dict[str, object]:
    return {
        "schema_kind": "disksage.reclaim-plan",
        "schema_version": 1,
        "operation": operation,
        "paths": [
            {
                "path": "/Users/example/Downloads/file.bin",
                "kind": "file",
                "files": 1,
                "dirs": 0,
                "skipped": 0,
                "estimate": _estimate(100, 4_096, operation=operation),
            },
            {
                "path": "/Users/example/Downloads/folder",
                "kind": "directory",
                "files": 2,
                "dirs": 1,
                "skipped": 0,
                "estimate": _estimate(200, 8_192, operation=operation),
            },
        ],
        "totals": _estimate(300, 12_288, operation=operation),
    }


def test_validate_reclaim_plan_returns_redacted_acceptance(client: TestClient):
    response = client.post("/api/reclaim-plan/validate", json=_reclaim_payload())

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "schema_version": 1,
        "schema_kind": "disksage.reclaim-plan",
    }
    assert "/Users/example" not in response.text
    assert "file.bin" not in response.text
    assert "12288" not in response.text


def test_validate_reclaim_plan_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/reclaim-plan/validate", json=_reclaim_payload()
        )

    assert response.status_code == 401


def test_validate_reclaim_plan_accepts_delete_with_unavailable_allocation(
    client: TestClient,
):
    payload = _reclaim_payload(operation="delete")
    for path_entry in payload["paths"]:
        path_entry["estimate"] = _estimate(
            path_entry["estimate"]["logical_bytes"],
            None,
            operation="delete",
        )
    payload["totals"] = _estimate(300, None, operation="delete")

    response = client.post("/api/reclaim-plan/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("schema_version", True),
        lambda payload: payload.__setitem__("schema_kind", "other"),
        lambda payload: payload.__setitem__("operation", "move"),
        lambda payload: payload.__setitem__("unknown_field", "rejected"),
        lambda payload: payload.__setitem__("paths", []),
        lambda payload: payload["paths"][0].__setitem__("path", "bad\x00path"),
        lambda payload: payload["paths"][0].__setitem__("path", "/" + "😀" * 1_024),
        lambda payload: payload["paths"][0].__setitem__("files", 0),
        lambda payload: payload["paths"][0].__setitem__("skipped", 1),
        lambda payload: payload["paths"][1].__setitem__("dirs", 0),
        lambda payload: payload["paths"].append(deepcopy(payload["paths"][0])),
        lambda payload: payload["paths"][0]["estimate"].__setitem__(
            "physically_reclaimable_bytes", 100
        ),
        lambda payload: payload["paths"][0]["estimate"].__setitem__(
            "status", "verified"
        ),
        lambda payload: payload["paths"][0]["estimate"]["reason_codes"].pop(),
        lambda payload: payload["totals"].__setitem__("logical_bytes", 299),
        lambda payload: payload["totals"].__setitem__("allocated_bytes", 12_289),
        lambda payload: payload["totals"].__setitem__("allocated_bytes", 8_191),
        lambda payload: payload["paths"][0]["estimate"].__setitem__(
            "allocated_bytes", None
        ),
        lambda payload: payload["paths"][0]["estimate"].__setitem__(
            "logical_bytes", 18_446_744_073_709_551_616
        ),
    ],
    ids=[
        "boolean-version",
        "wrong-schema-kind",
        "unsupported-operation",
        "unknown-field",
        "empty-paths",
        "control-character-path",
        "path-over-utf8-byte-limit",
        "file-kind-count-mismatch",
        "file-kind-skipped-mismatch",
        "directory-kind-count-mismatch",
        "duplicate-path",
        "invented-physical-reclaimability",
        "invented-status",
        "reason-code-mismatch",
        "logical-total-mismatch",
        "allocated-total-exceeds-path-sum",
        "allocated-total-below-largest-path",
        "mixed-allocation-availability",
        "u64-overflow",
    ],
)
def test_validate_reclaim_plan_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_reclaim_payload())
    mutate(payload)

    response = client.post("/api/reclaim-plan/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_reclaim_plan_invalid"}


def test_validate_reclaim_plan_rejects_delete_with_trash_reason(client: TestClient):
    payload = _reclaim_payload(operation="delete")
    payload["totals"]["reason_codes"].append("trash-retains-bytes-until-emptied")

    response = client.post("/api/reclaim-plan/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_reclaim_plan_invalid"}


def test_validate_reclaim_plan_rejects_duplicate_json_keys(client: TestClient):
    raw = json.dumps(_reclaim_payload(), separators=(",", ":"))
    raw = raw.replace('"schema_version":1', '"schema_version":2,"schema_version":1')

    response = client.post(
        "/api/reclaim-plan/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_reclaim_plan_invalid"}


def test_validate_reclaim_plan_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/reclaim-plan/validate",
        content=b"{" + b" " * MAX_DISKSAGE_RECLAIM_PLAN_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "disksage_reclaim_plan_too_large"}


def test_validate_reclaim_plan_accepts_full_path_collection_above_legacy_cap(
    client: TestClient,
):
    operation = "delete"
    paths = [
        {
            "path": f"/evidence/{index:04d}/" + "x" * 300,
            "kind": "file",
            "files": 1,
            "dirs": 0,
            "skipped": 0,
            "estimate": _estimate(1, 1, operation=operation),
        }
        for index in range(1_000)
    ]
    payload = {
        "schema_kind": "disksage.reclaim-plan",
        "schema_version": 1,
        "operation": operation,
        "paths": paths,
        "totals": _estimate(1_000, 1_000, operation=operation),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    assert 256 * 1024 < len(body) < MAX_DISKSAGE_RECLAIM_PLAN_BODY_BYTES

    response = client.post(
        "/api/reclaim-plan/validate",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200


def test_validate_reclaim_plan_has_no_database_dependency(client: TestClient):
    def fail_if_called():
        raise AssertionError("reclaim plan validation must not open a database session")

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post("/api/reclaim-plan/validate", json=_reclaim_payload())
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
