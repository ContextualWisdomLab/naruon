from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.cloud_source_eviction import (
    MAX_DISKSAGE_CLOUD_SOURCE_EVICTION_BODY_BYTES,
)
from db.session import get_db
from main import app


pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.fixture
def client():
    with TestClient(
        app, headers={"X-User-Id": "source-eviction-proof-user"}
    ) as test_client:
        yield test_client


def _remote_content(provider: str) -> dict[str, object] | None:
    if provider == "icloud":
        return None
    if provider == "onedrive":
        return {
            "object_id": "remote-item-1",
            "revision": "revision-1",
            "algorithm": "quick-xor",
            "checksum": "AQIDBA==",
            "location_bound": True,
            "location_proof": f"onedrive-path-v1:{'1' * 64}",
        }
    return {
        "object_id": "google-file-1",
        "revision": "revision-1",
        "algorithm": "sha256",
        "checksum": "2" * 64,
        "location_bound": True,
        "location_proof": f"google-drive-parent-chain-v1:{'3' * 64}",
    }


def _output(provider: str = "onedrive") -> dict[str, object]:
    receipt_id = "a" * 64
    evidence_record_id = "b" * 64
    approval_id = "c" * 64
    intent_id = "d" * 64
    completion_id = "e" * 64
    source = "/Users/example/Downloads/report.wav"
    destination = f"/Users/example/Cloud/{provider}/Archive/report.wav"
    confirmed_at_ms = 100
    evidence_kind = "provider-native-status" if provider == "icloud" else "provider-api"
    evidence_id = f"{evidence_kind}:{'4' * 64}"
    evidence = {
        "receipt_id": receipt_id,
        "provider": provider,
        "destination": destination,
        "observed_bytes": 4_096,
        "destination_blake3": "f" * 64,
        "confirmed_at_ms": confirmed_at_ms,
        "kind": evidence_kind,
        "evidence_id": evidence_id,
        "sync_complete": True,
        "remote_content": _remote_content(provider),
    }
    evidence_record = {
        "version": 1,
        "record_id": evidence_record_id,
        "evidence": deepcopy(evidence),
    }
    permit = {
        "receipt_id": receipt_id,
        "provider": provider,
        "source": source,
        "destination": destination,
        "bytes": 4_096,
        "blake3": "f" * 64,
        "approved_at_ms": confirmed_at_ms,
        "evidence_kind": evidence_kind,
        "evidence_id": evidence_id,
        "evidence_record_id": evidence_record_id,
    }
    evidence_path = (
        "/Users/example/AppData/cloud-provider-evidence/"
        f"{receipt_id}-{confirmed_at_ms:020}-{evidence_record_id}.json"
    )
    approval = {
        "version": 1,
        "approval_id": approval_id,
        "receipt_id": receipt_id,
        "evidence_record_id": evidence_record_id,
        "approved_at_ms": 102,
        "approved_by": "human:test-operator",
        "rationale": "Provider sync is complete and this source may move to Trash.",
        "active_use_observed_at_ms": 101,
        "active_use": {
            "method": "lsof-fp+ps-command",
            "evidence_complete": True,
            "active": False,
            "observed_pids": [],
            "results_truncated": False,
            "error": None,
        },
    }
    control_root = "/Users/example/AppData/cloud-source-evictions"
    return {
        "action": "attest-approve-and-trash-verified-cloud-source",
        "attestation": {
            "evidence": evidence,
            "assessment": {
                "state": "complete",
                "pending_age_ms": 0,
                "overdue_after_ms": 86_400_000,
                "reason_codes": [],
            },
            "evidence_record": evidence_record,
            "evidence_path": evidence_path,
            "permit": permit,
            "blockers": [],
        },
        "approval": approval,
        "approval_path": (
            "/Users/example/AppData/cloud-source-eviction-approvals/"
            f"{approval_id}.approval.json"
        ),
        "eviction": {
            "action": "trash-verified-cloud-source",
            "receipt_id": receipt_id,
            "intent_id": intent_id,
            "completion_id": completion_id,
            "evidence_record_id": evidence_record_id,
            "approval_id": approval_id,
            "source": source,
            "staged_source": (
                f"/Users/example/Downloads/.disksage-evict-{receipt_id}/report.wav"
            ),
            "intent_path": f"{control_root}/{receipt_id}.intent.json",
            "completion_path": f"{control_root}/{receipt_id}.complete.json",
            "source_trashed": True,
            "reconciled_after_interruption": False,
            "already_completed": False,
        },
    }


@pytest.mark.parametrize("provider", ["icloud", "onedrive", "google-drive"])
def test_validate_returns_redacted_acceptance(client: TestClient, provider: str):
    payload = _output(provider)

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "validation_scope": "schema-and-claim-consistency-only",
        "version": 1,
        "evidence_kind": "disksage.cloud-source-eviction",
        "evidence_stage": "execution",
    }
    assert "report.wav" not in response.text
    assert "4096" not in response.text
    assert "test-operator" not in response.text
    assert payload["approval"]["approval_id"] not in response.text
    assert payload["attestation"]["evidence"]["evidence_id"] not in response.text


def test_validate_requires_authentication():
    with TestClient(app) as anonymous_client:
        response = anonymous_client.post(
            "/api/cloud-source-eviction/validate",
            json=_output(),
        )

    assert response.status_code == 401


@pytest.mark.parametrize("provider", ["onedrive", "google-drive"])
def test_validate_accepts_complete_provider_native_evidence(
    client: TestClient,
    provider: str,
):
    payload = _output(provider)
    evidence = payload["attestation"]["evidence"]
    evidence.update(
        {
            "kind": "provider-native-status",
            "evidence_id": f"provider-native-status:{'5' * 64}",
            "remote_content": None,
        }
    )
    payload["attestation"]["evidence_record"]["evidence"] = deepcopy(evidence)
    payload["attestation"]["permit"].update(
        {
            "evidence_kind": evidence["kind"],
            "evidence_id": evidence["evidence_id"],
        }
    )

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "source_trashed,reconciled,already_completed",
    [
        (False, True, False),
        (False, False, True),
        (False, True, True),
    ],
    ids=["reconciled", "replayed", "replayed-reconciled"],
)
def test_validate_accepts_recovery_states(
    client: TestClient,
    source_trashed: bool,
    reconciled: bool,
    already_completed: bool,
):
    payload = _output()
    payload["eviction"].update(
        {
            "source_trashed": source_trashed,
            "reconciled_after_interruption": reconciled,
            "already_completed": already_completed,
        }
    )

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("unknown", "rejected"),
        lambda payload: payload["attestation"]["evidence"].__setitem__(
            "observed_bytes", True
        ),
        lambda payload: payload["attestation"]["evidence"].__setitem__(
            "receipt_id", "0" * 64
        ),
        lambda payload: payload["attestation"]["evidence_record"].__setitem__(
            "record_id", "0" * 64
        ),
        lambda payload: payload["attestation"]["evidence_record"][
            "evidence"
        ].__setitem__("destination", "/different/destination"),
        lambda payload: payload["attestation"].__setitem__("permit", None),
        lambda payload: payload["attestation"].__setitem__(
            "blockers", ["provider-sync-incomplete"]
        ),
        lambda payload: payload["attestation"]["assessment"].__setitem__(
            "state", "pending"
        ),
        lambda payload: payload["attestation"]["assessment"].__setitem__(
            "pending_age_ms", 1
        ),
        lambda payload: payload["attestation"]["permit"].__setitem__(
            "provider", "google-drive"
        ),
        lambda payload: payload["attestation"]["permit"].__setitem__(
            "evidence_id", "different"
        ),
        lambda payload: payload["approval"].__setitem__("evidence_record_id", "0" * 64),
        lambda payload: payload["eviction"].__setitem__("approval_id", "0" * 64),
        lambda payload: payload["eviction"].__setitem__(
            "source", "/Users/example/Downloads/other.wav"
        ),
    ],
    ids=[
        "unknown-field",
        "boolean-bytes",
        "evidence-receipt-binding",
        "record-id-binding",
        "record-evidence-binding",
        "missing-permit",
        "nonempty-blockers",
        "timeliness-state",
        "timeliness-age",
        "permit-provider-binding",
        "permit-evidence-binding",
        "approval-evidence-binding",
        "result-approval-binding",
        "result-source-binding",
    ],
)
def test_validate_cross_bindings_fail_closed(client: TestClient, mutate):
    payload = deepcopy(_output())
    mutate(payload)

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_source_eviction_invalid"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["approval"].__setitem__("version", True),
        lambda payload: payload["approval"].__setitem__("approval_id", "C" * 64),
        lambda payload: payload["approval"].__setitem__(
            "approved_by", "agent:test-operator"
        ),
        lambda payload: payload["approval"].__setitem__("rationale", "   "),
        lambda payload: payload["approval"].__setitem__("rationale", "bad\u0000text"),
        lambda payload: payload["approval"].__setitem__(
            "active_use_observed_at_ms", 99
        ),
        lambda payload: payload["approval"].__setitem__(
            "active_use_observed_at_ms", 103
        ),
        lambda payload: payload["approval"]["active_use"].update(
            {"active": True, "observed_pids": [42]}
        ),
        lambda payload: payload["approval"]["active_use"].update(
            {"evidence_complete": False, "results_truncated": True}
        ),
        lambda payload: payload["approval"]["active_use"].update(
            {"evidence_complete": False, "error": "probe failed"}
        ),
    ],
    ids=[
        "boolean-version",
        "uppercase-id",
        "non-human",
        "blank-rationale",
        "control-rationale",
        "observation-before-permit",
        "observation-after-approval",
        "active-source",
        "truncated-observation",
        "probe-error",
    ],
)
def test_validate_approval_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_output())
    mutate(payload)

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_source_eviction_invalid"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["attestation"]["evidence"][
            "remote_content"
        ].__setitem__("algorithm", "sha256"),
        lambda payload: payload["attestation"]["evidence"][
            "remote_content"
        ].__setitem__("location_bound", False),
        lambda payload: payload["attestation"]["evidence"][
            "remote_content"
        ].__setitem__("location_proof", f"wrong:{'1' * 64}"),
        lambda payload: payload["attestation"]["evidence"].__setitem__(
            "sync_complete", False
        ),
        lambda payload: payload["attestation"]["evidence"].__setitem__(
            "remote_content", None
        ),
    ],
    ids=[
        "provider-algorithm",
        "location-unbound",
        "location-proof-prefix",
        "sync-incomplete",
        "remote-proof-missing",
    ],
)
def test_validate_provider_evidence_fails_closed(client: TestClient, mutate):
    payload = deepcopy(_output("onedrive"))
    mutate(payload)
    payload["attestation"]["evidence_record"]["evidence"] = deepcopy(
        payload["attestation"]["evidence"]
    )

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_source_eviction_invalid"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__(
            "approval_path", "/Users/example/AppData/wrong.approval.json"
        ),
        lambda payload: payload["attestation"].__setitem__(
            "evidence_path", "/Users/example/AppData/wrong.json"
        ),
        lambda payload: payload["eviction"].__setitem__(
            "staged_source", "/Users/example/Downloads/report.wav"
        ),
        lambda payload: payload["eviction"].__setitem__(
            "intent_path", "/Users/example/AppData/wrong.intent.json"
        ),
        lambda payload: payload["eviction"].__setitem__(
            "completion_path", payload["eviction"]["intent_path"]
        ),
        lambda payload: payload["eviction"].__setitem__(
            "intent_path", payload["eviction"]["source"]
        ),
        lambda payload: payload["eviction"].update(
            {
                "source_trashed": False,
                "reconciled_after_interruption": False,
                "already_completed": False,
            }
        ),
        lambda payload: payload["eviction"].update(
            {
                "source_trashed": True,
                "reconciled_after_interruption": True,
            }
        ),
    ],
    ids=[
        "approval-filename",
        "evidence-filename",
        "staging-binding",
        "intent-filename",
        "record-alias",
        "control-data-alias",
        "impossible-empty-state",
        "contradictory-trash-state",
    ],
)
def test_validate_paths_and_result_state_fail_closed(client: TestClient, mutate):
    payload = deepcopy(_output())
    mutate(payload)

    response = client.post("/api/cloud-source-eviction/validate", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_source_eviction_invalid"}


def test_validate_rejects_duplicate_json_keys(client: TestClient):
    raw = json.dumps(_output(), separators=(",", ":"))
    raw = raw.replace(
        '"source_trashed":true',
        '"source_trashed":false,"source_trashed":true',
    )

    response = client.post(
        "/api/cloud-source-eviction/validate",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "disksage_cloud_source_eviction_invalid"}


def test_validate_caps_raw_body(client: TestClient):
    response = client.post(
        "/api/cloud-source-eviction/validate",
        content=b"{" + b" " * MAX_DISKSAGE_CLOUD_SOURCE_EVICTION_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "disksage_cloud_source_eviction_too_large"}


def test_validate_has_no_database_dependency(client: TestClient):
    def fail_if_called():
        raise AssertionError(
            "source eviction validation must not open a database session"
        )

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail_if_called
    try:
        response = client.post(
            "/api/cloud-source-eviction/validate",
            json=_output(),
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 200
