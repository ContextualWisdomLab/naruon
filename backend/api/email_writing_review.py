"""Authenticated advisory HTTP boundary for email-writing review."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.session import get_db
from services.email_writing_contracts import EmailWritingReviewRequest, EmailWritingReviewResponse
from services.email_writing_review_service import (
    EmailWritingReviewService,
    EmailWritingReviewServiceError,
)

router = APIRouter(prefix="/api/email-writing", tags=["email-writing"])

PublicReviewErrorCode = Literal[
    "email_unavailable",
    "review_owner_scope_unavailable",
    "review_evidence_unavailable",
    "review_timeout",
    "provider_unavailable",
    "review_runtime_unavailable",
    "review_unavailable",
]
_PUBLIC_SERVICE_ERROR_CODES = frozenset(
    {
        "email_unavailable",
        "review_owner_scope_unavailable",
        "review_evidence_unavailable",
        "review_timeout",
        "provider_unavailable",
    }
)


class EmailWritingReviewErrorResponse(BaseModel):
    """Bounded public error envelope that never carries causal service text."""

    model_config = ConfigDict(extra="forbid", strict=True)

    error_code: PublicReviewErrorCode


def get_email_writing_review_service() -> EmailWritingReviewService | None:
    """Return the assembled review runtime only after immutable dependencies are admitted.

    Task 10 deliberately exposes no fallback implementation. Until the exact
    fast-mlsirm distributable, policy, and runtime wiring are admitted on the
    current stack, the HTTP route reports typed unavailability while ordinary
    mail editing and sending remain outside this endpoint and unaffected.
    """
    return None


def _error_response(
    *,
    status_code: int,
    error_code: PublicReviewErrorCode,
) -> JSONResponse:
    """Serialize one validated public error envelope without internal exception data."""
    payload = EmailWritingReviewErrorResponse(error_code=error_code)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _service_error_response(error: EmailWritingReviewServiceError) -> JSONResponse:
    """Map only allowlisted service codes to public responses and mask everything else."""
    if error.code == "email_unavailable":
        status_code = 404
    elif error.code == "review_owner_scope_unavailable":
        status_code = 403
    else:
        status_code = 503

    if error.code in _PUBLIC_SERVICE_ERROR_CODES:
        public_code = cast(PublicReviewErrorCode, error.code)
    else:
        public_code = "review_unavailable"
    return _error_response(status_code=status_code, error_code=public_code)


@router.post(
    "/review",
    response_model=EmailWritingReviewResponse,
    responses={
        403: {"model": EmailWritingReviewErrorResponse},
        404: {"model": EmailWritingReviewErrorResponse},
        503: {"model": EmailWritingReviewErrorResponse},
    },
)
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
        return _error_response(
            status_code=503,
            error_code="review_runtime_unavailable",
        )
    try:
        return await review_service.review(db, auth_context, request)
    except EmailWritingReviewServiceError as error:
        return _service_error_response(error)
