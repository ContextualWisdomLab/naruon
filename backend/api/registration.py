"""Public self-registration relay to the IdP-side account-registration API.

Naruon owns the signup page; account creation itself belongs to the identity
platform (keyverse account-unification service). This router is the only
anonymous surface in the backend: it validates the submission, then relays it
with the dedicated registration bearer token over a strictly allowlisted
egress URL. Every failure maps to a deterministic ``error_code`` and the
surface fails closed (``registration_unavailable``) whenever the relay is not
fully configured.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import settings
from core.url_validation import parse_allowed_hosts

logger = logging.getLogger(__name__)

registration_router = APIRouter(prefix="/api/auth", tags=["registration"])

EMAIL_MAX_LENGTH = 254
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
NAME_MAX_LENGTH = 100
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
RELAY_TIMEOUT_SECONDS = 10.0

REGISTRATION_RATE_LIMIT_WINDOW_SECONDS = 300.0
REGISTRATION_RATE_LIMIT_MAX_ATTEMPTS = 30
_attempt_lock = threading.Lock()
_attempt_window_start = 0.0
_attempt_count = 0


class RegistrationRequest(BaseModel):
    """One signup submission from the Naruon registration page."""

    email_address: str = Field(min_length=3, max_length=EMAIL_MAX_LENGTH)
    initial_password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )
    first_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    last_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)


class RegistrationResponse(BaseModel):
    """Outcome the signup page needs; internals never leak."""

    email_address: str


def _registration_error(status_code: int, error_code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error_code": error_code})


def _record_attempt() -> None:
    """Enforce a coarse fixed-window rate limit on signup attempts."""
    global _attempt_window_start, _attempt_count
    now = time.monotonic()
    with _attempt_lock:
        if now - _attempt_window_start > REGISTRATION_RATE_LIMIT_WINDOW_SECONDS:
            _attempt_window_start = now
            _attempt_count = 0
        _attempt_count += 1
        if _attempt_count > REGISTRATION_RATE_LIMIT_MAX_ATTEMPTS:
            raise _registration_error(429, "registration_rate_limited")


def _registration_relay_target() -> tuple[str, str]:
    """Return (url, token) for the IdP registration API, failing closed."""
    service_url = (settings.REGISTRATION_SERVICE_URL or "").strip()
    token = settings.REGISTRATION_SERVICE_TOKEN
    allowed_hosts = parse_allowed_hosts(settings.ALLOWED_REGISTRATION_SERVICE_HOSTS)
    if not service_url or token is None or not allowed_hosts:
        raise _registration_error(503, "registration_unavailable")
    token_value = token.get_secret_value().strip()
    if not token_value:
        raise _registration_error(503, "registration_unavailable")
    try:
        host = (urlsplit(service_url).hostname or "").lower()
    except ValueError:
        raise _registration_error(503, "registration_unavailable") from None
    if not host or host not in allowed_hosts:
        logger.warning("registration relay host is not allowlisted; refusing")
        raise _registration_error(503, "registration_unavailable")
    return service_url.rstrip("/"), token_value


def _validated_email(raw_email: str) -> str:
    email_address = raw_email.strip().lower()
    if (
        len(email_address) > EMAIL_MAX_LENGTH
        or CONTROL_CHARACTER_PATTERN.search(email_address)
        or not EMAIL_PATTERN.match(email_address)
    ):
        raise _registration_error(422, "invalid_email_address")
    return email_address


async def submit_registration_to_service(
    service_url: str, token_value: str, payload: dict[str, str | None]
) -> httpx.Response:
    """POST the registration to the IdP-side API (patchable seam for tests)."""
    async with httpx.AsyncClient(timeout=RELAY_TIMEOUT_SECONDS) as client:
        return await client.post(
            f"{service_url}/registration/accounts",
            json=payload,
            headers={"Authorization": f"Bearer {token_value}"},
        )


@registration_router.post("/register", response_model=RegistrationResponse)
async def register_account(request_body: RegistrationRequest) -> RegistrationResponse:
    """Relay one signup to the identity platform's registration API."""
    _record_attempt()
    service_url, token_value = _registration_relay_target()
    email_address = _validated_email(request_body.email_address)
    if CONTROL_CHARACTER_PATTERN.search(request_body.initial_password):
        raise _registration_error(422, "invalid_password")

    payload: dict[str, str | None] = {
        "email_address": email_address,
        "initial_password": request_body.initial_password,
        "first_name": request_body.first_name,
        "last_name": request_body.last_name,
    }
    try:
        response = await submit_registration_to_service(
            service_url, token_value, payload
        )
    except httpx.HTTPError:
        logger.warning("registration relay request failed", exc_info=True)
        raise _registration_error(503, "registration_unavailable") from None

    if response.status_code == 201:
        return RegistrationResponse(email_address=email_address)
    if response.status_code == 409:
        raise _registration_error(409, "email_already_registered")
    if response.status_code == 422:
        raise _registration_error(422, "invalid_registration_request")
    if response.status_code == 429:
        raise _registration_error(429, "registration_rate_limited")
    logger.warning(
        "registration relay returned unexpected status %d", response.status_code
    )
    raise _registration_error(503, "registration_unavailable")
