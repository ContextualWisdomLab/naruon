"""Authenticated advisory HTTP boundary for email-writing review."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.session import get_db
from services.email_writing_contracts import EmailWritingReviewRequest, EmailWritingReviewResponse
from services.email_writing_review_service import (
    EmailWritingReviewService,
    EmailWritingReviewServiceError,
)

router = APIRouter(prefix="/api/email-writing", tags=["email-writing"])


def get_email_writing_review_service() -> EmailWritingReviewService | None:
    """Return the assembled review runtime only after immutable dependencies are admitted.

    Task 10 deliberately exposes no fallback implementation. Until the exact
    fast-mlsirm distributable, policy, and runtime wiring are admitted on the
    current stack, the HTTP route reports typed unavailability while ordinary
    mail editing and sending remain outside this endpoint and unaffected.
    """
    return None


def _service_error_response(error: EmailWritingReviewServiceError) -> JSONResponse:
    """Map redacted service codes to bounded HTTP states without causal payloads."""
    if error.code == "email_unavailable":
        status_code = 404
    elif error.code == "review_owner_scope_unavailable":
        status_code = 403
    else:
        status_code = 503
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error.code},
    )


@router.post("/review", response_model=EmailWritingReviewResponse)
async def review_email_writing(
    request: EmailWritingReviewRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
    review_service: EmailWritingReviewService | None = Depends(
        get_email_writing_review_service
    ),
) -> EmailWritingReviewResponse | JSONResponse:
    """Run one advisory review without gaining authority to mutate or send mail."""
    if review_service is None:
        return JSONResponse(
            status_code=503,
            content={"error_code": "review_runtime_unavailable"},
        )
    try:
        return await review_service.review(db, auth_context, request)
    except EmailWritingReviewServiceError as error:
        return _service_error_response(error)
