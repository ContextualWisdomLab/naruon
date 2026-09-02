"""HTTP contract for advisory email-writing review."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth import AuthContext, get_auth_context
from api.email_writing_review import get_email_writing_review_service, router
from db.session import get_db
from services.email_writing_contracts import (
    EmailWritingDocumentGuidance,
    EmailWritingDocumentRevision,
    EmailWritingProvenance,
    EmailWritingReviewRequest,
    EmailWritingReviewResponse,
)
from services.email_writing_review_service import EmailWritingReviewServiceError

_ROUTE = "/api/email-writing/review"
_DRAFT = "Please send the signed report by Friday."
_DIGEST = hashlib.sha256(_DRAFT.encode("utf-8")).hexdigest()


class _Session:
    """Opaque persistence boundary passed unchanged to the injected service."""


class _ReviewService:
    """Record the authorized API inputs and return one advisory response."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, AuthContext, EmailWritingReviewRequest]] = []
        self.error_code: str | None = None

    async def review(
        self,
        session: object,
        auth_context: AuthContext,
        request: EmailWritingReviewRequest,
    ) -> EmailWritingReviewResponse:
        self.calls.append((session, auth_context, request))
        if self.error_code is not None:
            raise EmailWritingReviewServiceError(self.error_code)
        return EmailWritingReviewResponse(
            review_session_id="review_session_test",
            document_revision=request.document_revision,
            projection_name=request.projection_name,
            projection_version=request.projection_version,
            review_status="abstained",
            diagnostics=[],
            document_guidance=EmailWritingDocumentGuidance(
                purpose_summary="",
                reader_interpretation="",
                missing_requests=[],
                structure_suggestion="",
            ),
            context_limitations=["candidate_empty"],
            abstained_claims=[],
            provenance=EmailWritingProvenance(
                workflow_id="email-writing-review",
                workflow_version="task10-test",
                judge_policy_version="evaluation-only",
                rubric_version="adr-0005-v1",
                model_profile_id="test-profile",
                orchestration_mode="route",
                prompt_hash="sha256:" + hashlib.sha256(b"").hexdigest(),
            ),
        )


def _request_payload() -> dict[str, Any]:
    return {
        "source_email_id": 17,
        "document_revision": {
            "algorithm": "SHA-256",
            "digest_hex": _DIGEST,
            "strong_entity_tag": f'"sha256-{_DIGEST}"',
        },
        "projection_name": "inkspan-prosemirror-text",
        "projection_version": 1,
        "draft_plain_text": _DRAFT,
        "language_tag": "en",
        "review_mode": "incremental",
        "changed_selector": {
            "type": "TextPositionSelector",
            "start": 0,
            "end": len(_DRAFT),
        },
        "reply_objective": "Request the signed report without weakening Friday's deadline.",
    }


@pytest.fixture
def review_service() -> _ReviewService:
    return _ReviewService()


@pytest.fixture
def client(review_service: _ReviewService) -> AsyncIterator[TestClient]:
    application = FastAPI()
    application.include_router(router, dependencies=[Depends(get_auth_context)])
    session = _Session()
    auth_context = AuthContext(
        user_id="user_alpha",
        role="member",
        organization_id="organization_alpha",
        group_ids=(),
        workspace_id="workspace_alpha",
    )

    async def override_auth_context() -> AuthContext:
        return auth_context

    async def override_get_db():
        yield session

    def override_review_service() -> _ReviewService:
        return review_service

    application.dependency_overrides[get_auth_context] = override_auth_context
    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_email_writing_review_service] = override_review_service

    with TestClient(application) as test_client:
        test_client._review_test_session = session  # type: ignore[attr-defined]
        test_client._review_test_auth = auth_context  # type: ignore[attr-defined]
        yield test_client


def test_review_api_passes_authorized_scope_and_returns_advisory_status(
    client: TestClient,
    review_service: _ReviewService,
) -> None:
    response = client.post(_ROUTE, json=_request_payload())

    assert response.status_code == 200
    assert response.json()["review_status"] == "abstained"
    assert response.json()["diagnostics"] == []
    assert len(review_service.calls) == 1
    session, auth_context, request = review_service.calls[0]
    assert session is client._review_test_session  # type: ignore[attr-defined]
    assert auth_context is client._review_test_auth  # type: ignore[attr-defined]
    assert request.source_email_id == 17
    assert request.draft_plain_text == _DRAFT


@pytest.mark.parametrize(
    ("error_code", "expected_status"),
    [
        ("email_unavailable", 404),
        ("review_owner_scope_unavailable", 403),
        ("review_evidence_unavailable", 503),
        ("provider_unavailable", 503),
    ],
)
def test_review_api_maps_redacted_service_failures_without_raw_exception_text(
    client: TestClient,
    review_service: _ReviewService,
    error_code: str,
    expected_status: int,
) -> None:
    review_service.error_code = error_code

    response = client.post(_ROUTE, json=_request_payload())

    assert response.status_code == expected_status
    assert response.json() == {"error_code": error_code}
    assert "Traceback" not in response.text


def test_review_api_fails_closed_when_runtime_is_not_assembled() -> None:
    application = FastAPI()
    application.include_router(router, dependencies=[Depends(get_auth_context)])
    auth_context = AuthContext(
        user_id="user_alpha",
        role="member",
        organization_id="organization_alpha",
        group_ids=(),
        workspace_id="workspace_alpha",
    )

    async def override_auth_context() -> AuthContext:
        return auth_context

    async def override_get_db():
        yield _Session()

    application.dependency_overrides[get_auth_context] = override_auth_context
    application.dependency_overrides[get_db] = override_get_db

    with TestClient(application) as test_client:
        response = test_client.post(_ROUTE, json=_request_payload())

    assert response.status_code == 503
    assert response.json() == {"error_code": "review_runtime_unavailable"}


def test_review_api_rejects_invalid_transport_before_service_call(
    client: TestClient,
    review_service: _ReviewService,
) -> None:
    payload = _request_payload()
    payload["source_email_id"] = 0

    response = client.post(_ROUTE, json=payload)

    assert response.status_code == 422
    assert review_service.calls == []
