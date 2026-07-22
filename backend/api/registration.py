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
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import settings
from core.url_validation import parse_allowed_hosts, validate_https_url_host_details
from services.llm_provider_urls import build_pinned_validated_url_async_client

logger = logging.getLogger(__name__)

registration_router = APIRouter(prefix="/api/auth", tags=["registration"])

EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
NAME_MAX_LENGTH = 100
RELAY_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class RegistrationRelayTarget:
    """Validated, DNS-pinned identity-platform registration destination."""

    endpoint_url: str
    token_value: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


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


def _registration_relay_target() -> RegistrationRelayTarget:
    """Return the validated IdP registration API target, failing closed."""
    service_url = (settings.REGISTRATION_SERVICE_URL or "").strip()
    token = settings.REGISTRATION_SERVICE_TOKEN
    allowed_hosts = parse_allowed_hosts(settings.ALLOWED_REGISTRATION_SERVICE_HOSTS)
    if not service_url or token is None or not allowed_hosts:
        raise _registration_error(503, "registration_unavailable")
    token_value = token.get_secret_value().strip()
    if not token_value:
        raise _registration_error(503, "registration_unavailable")
    try:
        validated = validate_https_url_host_details(
            "REGISTRATION_SERVICE_URL",
            service_url,
            allowed_hosts,
            "ALLOWED_REGISTRATION_SERVICE_HOSTS",
            allow_local=settings.ALLOW_LOCAL_REGISTRATION_SERVICE,
        )
        parsed = urlsplit(validated.normalized_url)
    except ValueError:
        raise _registration_error(503, "registration_unavailable") from None
    if parsed.path not in ("", "/") or parsed.query:
        logger.warning("registration relay URL must be a clean origin; refusing")
        raise _registration_error(503, "registration_unavailable")
    endpoint_url = urlunsplit(
        (parsed.scheme, parsed.netloc, "/registration/accounts", "", "")
    )
    return RegistrationRelayTarget(
        endpoint_url=endpoint_url,
        token_value=token_value,
        hostname=validated.hostname,
        port=validated.port,
        addresses=validated.addresses,
    )


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _validated_email(raw_email: str) -> str:
    email_address = raw_email.strip()
    if len(email_address) > EMAIL_MAX_LENGTH or _has_control_character(email_address):
        raise _registration_error(422, "invalid_email_address")
    try:
        normalized = validate_email(
            email_address, check_deliverability=False
        ).normalized
    except EmailNotValidError:
        raise _registration_error(422, "invalid_email_address")
    return normalized.lower()


async def submit_registration_to_service(
    target: RegistrationRelayTarget, payload: dict[str, str | None]
) -> httpx.Response:
    """POST the registration to the IdP-side API (patchable seam for tests)."""
    client = build_pinned_validated_url_async_client(
        normalized_url=target.endpoint_url,
        hostname=target.hostname,
        port=target.port,
        addresses=target.addresses,
    )
    async with client:
        return await client.post(
            target.endpoint_url,
            json=payload,
            headers={"Authorization": f"Bearer {target.token_value}"},
            timeout=RELAY_TIMEOUT_SECONDS,
        )


@registration_router.post("/register", response_model=RegistrationResponse)
async def register_account(request_body: RegistrationRequest) -> RegistrationResponse:
    """Relay one signup to the identity platform's registration API."""
    target = _registration_relay_target()
    email_address = _validated_email(request_body.email_address)
    if _has_control_character(request_body.initial_password):
        raise _registration_error(422, "invalid_password")

    payload: dict[str, str | None] = {
        "email_address": email_address,
        "initial_password": request_body.initial_password,
        "first_name": request_body.first_name,
        "last_name": request_body.last_name,
    }
    try:
        response = await submit_registration_to_service(target, payload)
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
