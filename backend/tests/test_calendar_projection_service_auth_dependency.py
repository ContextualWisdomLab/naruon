"""Dependency-level failure accounting for calendar projection service auth."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api import auth as auth_module
from api.calendar_projection_auth import get_calendar_projection_service_context
from core.config import settings


@pytest.mark.asyncio
async def test_oidc_unavailability_is_not_counted_as_bad_service_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_tokens: list[str] = []
    monkeypatch.setattr(settings, "OIDC_ISSUER_URL", None)
    monkeypatch.setattr(auth_module, "_cached_oidc_signing_keys", ())
    monkeypatch.setattr(
        auth_module,
        "_record_session_auth_failure",
        recorded_tokens.append,
    )

    with pytest.raises(HTTPException) as captured:
        await get_calendar_projection_service_context(
            authorization="Bearer opaque-service-token"
        )

    assert captured.value.status_code == 503
    assert recorded_tokens == []
