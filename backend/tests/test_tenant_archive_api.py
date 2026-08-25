"""API tests for the private tenant archive routes.

Exercises the real signed bearer-session authentication path (HMAC token
signed with the test control-plane secret) against a mocked database session,
following the conventions in ``tests/test_tasks_api.py``.
"""

import base64
import hashlib
import hmac
import json
import os
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from core.config import settings
from db.session import get_db
from main import app

from tests.test_tenant_archive_service import (
    MockArchiveSession,
    build_valid_bundle,
    make_email,
    make_task,
)

TEST_SESSION_HMAC_SECRET = os.environ["AUTH_SESSION_HMAC_SECRET"]


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token(payload: dict[str, object]) -> str:
    header_segment = _base64url_encode(
        json.dumps(
            {"alg": "HS256", "typ": "JWT"}, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        TEST_SESSION_HMAC_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _valid_session_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ver": 1,
        "iss": "naruon-control-plane",
        "aud": "naruon-api",
        "sub": "alice",
        "role": "member",
        "org": "org-acme",
        "groups": [],
        "workspace": "workspace-org-acme",
        "exp": int(time.time()) + 300,
    }
    payload.update(overrides)
    return payload


def _post_with_signed_session(path: str, json_body: dict | None = None):
    previous_secret = settings.AUTH_SESSION_HMAC_SECRET
    settings.AUTH_SESSION_HMAC_SECRET = SecretStr(TEST_SESSION_HMAC_SECRET)
    token = _signed_session_token(_valid_session_payload())
    try:
        with TestClient(
            app,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            return client.post(path, json=json_body)
    finally:
        settings.AUTH_SESSION_HMAC_SECRET = previous_secret


mock_session = MockArchiveSession()


@pytest.fixture(autouse=True)
def override_get_db():
    app.dependency_overrides[get_db] = lambda: mock_session
    yield
    app.dependency_overrides.pop(get_db, None)
    mock_session.emails = []
    mock_session.tasks = []


def test_export_requires_signed_bearer_session():
    response = TestClient(app).post("/api/tenant-archive/export")

    assert response.status_code == 401


def test_import_requires_signed_bearer_session():
    response = TestClient(app).post(
        "/api/tenant-archive/import", json={"bundle": build_valid_bundle()}
    )

    assert response.status_code == 401


def test_export_returns_scoped_bundle_for_signed_session():
    scoped_email = make_email(message_id="<scoped@example.com>")
    foreign_email = make_email(message_id="<foreign@example.com>")
    foreign_email.user_id = "mallory"
    mock_session.emails.extend([scoped_email, foreign_email])
    mock_session.tasks.append(make_task())

    response = _post_with_signed_session("/api/tenant-archive/export")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["manifest"]["archive_kind"] == "naruon_tenant_archive"
    assert body["manifest"]["source_scope"]["organization_id"] == "org-acme"
    exported_ids = {
        record["message_id"] for record in body["records"]["emails"]
    }
    assert exported_ids == {"<scoped@example.com>"}
    assert len(body["records"]["ticket_tasks"]) == 1


def test_import_accepts_signed_bundle_and_returns_summary():
    response = _post_with_signed_session(
        "/api/tenant-archive/import", {"bundle": build_valid_bundle()}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["emails"]["imported"] == 1
    assert body["emails"]["skipped_duplicate"] == 0
    assert body["ticket_tasks"]["imported"] == 0
    assert any(
        email.message_id == "<clean@example.com>"
        for email in mock_session.emails
    )


def test_import_rejects_request_extra_fields():
    bundle = build_valid_bundle()

    response = _post_with_signed_session(
        "/api/tenant-archive/import",
        {"bundle": bundle, "unexpected": True},
    )

    assert response.status_code == 422
    error_locations = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert ("body", "unexpected") in error_locations


def _assert_deterministic_error_code(
    mutator, expected_status: int, expected_error_code: str
) -> None:
    """POST a mutated valid bundle and assert the deterministic error code."""
    bundle = build_valid_bundle()
    mutator(bundle)
    response = _post_with_signed_session(
        "/api/tenant-archive/import", {"bundle": bundle}
    )
    assert response.status_code == expected_status, response.text
    assert response.json()["detail"]["error_code"] == expected_error_code


def test_import_maps_schema_unsupported_to_deterministic_error_code():
    def bump_version(bundle):
        bundle["manifest"]["schema_version"] = 99

    _assert_deterministic_error_code(bump_version, 422, "archive_schema_unsupported")


def test_import_maps_scope_mismatch_to_deterministic_error_code():
    def swap_scope(bundle):
        bundle["manifest"]["source_scope"]["organization_id"] = "org-other"

    _assert_deterministic_error_code(swap_scope, 403, "archive_scope_mismatch")


def test_import_maps_malformed_bundle_to_deterministic_error_code():
    def drop_records(bundle):
        bundle.pop("records")

    _assert_deterministic_error_code(drop_records, 422, "archive_bundle_malformed")


def test_archive_payloads_never_expose_sequential_database_ids():
    email_row = make_email(message_id="<opaque@example.com>")
    email_row.id = 4242
    task_row = make_task(task_uid="taskuidopaque000000000000000001")
    task_row.id = 5151
    mock_session.emails.append(email_row)
    mock_session.tasks.append(task_row)

    export_response = _post_with_signed_session("/api/tenant-archive/export")

    assert export_response.status_code == 200, export_response.text
    serialized_export = json.dumps(export_response.json())
    assert '"id"' not in serialized_export
    assert "4242" not in serialized_export
    assert "5151" not in serialized_export
