"""Audience-scoped service authentication for calendar read projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Header, HTTPException

from api import auth as auth_module
from core.config import settings

CALENDAR_PROJECTION_AUDIENCE = "naruon-calendar-read"
CALENDAR_PROJECTION_REQUIRED_SCOPE = "calendar:read"
_REQUIRED_CLAIMS = (
    "exp",
    "iss",
    "aud",
    "sub",
    "organization_id",
    "workspace_id",
    "scope",
)
_MAX_CLAIM_LENGTH = 256


@dataclass(frozen=True)
class CalendarProjectionServiceContext:
    """Verified service identity and exact tenant/workspace projection scope."""

    service_subject: str
    organization_id: str
    workspace_id: str
    audience: str
    scopes: frozenset[str]


def _authentication_failed() -> HTTPException:
    """Return one non-disclosing invalid-service-token response."""

    return HTTPException(
        status_code=401,
        detail="Calendar projection service authentication failed",
    )


def _authentication_unavailable() -> HTTPException:
    """Return one fail-closed operator-configuration response."""

    return HTTPException(
        status_code=503,
        detail="Calendar projection service authentication unavailable",
    )


def _extract_bearer_token(authorization: str | None) -> str:
    """Extract one exact bearer token without echoing it in errors."""

    if authorization is None or authorization != authorization.strip():
        raise _authentication_failed()
    scheme, separator, token = authorization.partition(" ")
    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not token
        or token != token.strip()
        or any(character.isspace() for character in token)
    ):
        raise _authentication_failed()
    return token


def _required_opaque_claim(
    payload: dict[str, Any],
    name: str,
) -> str:
    """Return a bounded ASCII non-URL token claim."""

    value = payload.get(name)
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or len(value) > _MAX_CLAIM_LENGTH
        or not value.isascii()
        or any(character.isspace() for character in value)
        or "://" in value
    ):
        raise _authentication_failed()
    return value


def _scope_values(payload: dict[str, Any]) -> frozenset[str]:
    """Normalize a JWT scope string or list into bounded ASCII tokens."""

    value = payload.get("scope")
    raw_scopes: list[Any]
    if isinstance(value, str):
        raw_scopes = value.split(" ")
    elif isinstance(value, list):
        raw_scopes = value
    else:
        raise _authentication_failed()

    scopes: set[str] = set()
    for raw_scope in raw_scopes:
        if (
            not isinstance(raw_scope, str)
            or raw_scope != raw_scope.strip()
            or not raw_scope
            or len(raw_scope) > _MAX_CLAIM_LENGTH
            or not raw_scope.isascii()
            or any(character.isspace() for character in raw_scope)
            or "://" in raw_scope
        ):
            raise _authentication_failed()
        scopes.add(raw_scope)
    if CALENDAR_PROJECTION_REQUIRED_SCOPE not in scopes:
        raise _authentication_failed()
    return frozenset(scopes)


def _unverified_key_id(token: str) -> str:
    """Return the exact RS256 key identifier or fail closed."""

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise _authentication_failed() from None
    if header.get("alg") != "RS256" or "crit" in header:
        raise _authentication_failed()
    key_id = header.get("kid")
    if (
        not isinstance(key_id, str)
        or key_id != key_id.strip()
        or not key_id
        or len(key_id) > _MAX_CLAIM_LENGTH
        or not key_id.isascii()
    ):
        raise _authentication_failed()
    return key_id


def _decode_with_cached_key(token: str) -> dict[str, Any]:
    """Verify one token against exactly one startup-cached OIDC signing key."""

    if not settings.OIDC_ISSUER_URL or not auth_module._cached_oidc_signing_keys:
        raise _authentication_unavailable()
    key_id = _unverified_key_id(token)
    matching_keys = tuple(
        signing_key
        for signing_key in auth_module._cached_oidc_signing_keys
        if getattr(signing_key, "key_id", None) == key_id
    )
    if len(matching_keys) != 1:
        raise _authentication_failed()
    try:
        payload = jwt.decode(
            token,
            matching_keys[0].key,
            algorithms=["RS256"],
            audience=CALENDAR_PROJECTION_AUDIENCE,
            issuer=settings.OIDC_ISSUER_URL,
            options={
                "require": _REQUIRED_CLAIMS,
                "verify_signature": True,
            },
        )
    except jwt.PyJWTError:
        raise _authentication_failed() from None
    if not isinstance(payload, dict):
        raise _authentication_failed()
    return payload


def decode_calendar_projection_service_token(
    token: str,
) -> CalendarProjectionServiceContext:
    """Verify one LineageWeave-facing service token and return its scope."""

    if not isinstance(token, str) or not token:
        raise _authentication_failed()
    payload = _decode_with_cached_key(token)
    scopes = _scope_values(payload)
    return CalendarProjectionServiceContext(
        service_subject=_required_opaque_claim(payload, "sub"),
        organization_id=_required_opaque_claim(payload, "organization_id"),
        workspace_id=_required_opaque_claim(payload, "workspace_id"),
        audience=CALENDAR_PROJECTION_AUDIENCE,
        scopes=scopes,
    )


async def get_calendar_projection_service_context(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> CalendarProjectionServiceContext:
    """FastAPI dependency for a verified calendar-projection service token."""

    token = _extract_bearer_token(authorization)
    auth_module._reject_if_session_auth_rate_limited(token)
    try:
        context = decode_calendar_projection_service_token(token)
    except HTTPException as exc:
        if exc.status_code == 401:
            auth_module._record_session_auth_failure(token)
        raise
    auth_module._clear_session_auth_failures(token)
    return context
