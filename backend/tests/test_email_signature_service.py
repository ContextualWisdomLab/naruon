"""Behavior contracts for scoped plain-text outbound email signatures."""

from __future__ import annotations

from typing import Any

import pytest

from db.email_signature_models import EmailSignatureProfile
from services.email_signature_service import (
    EMAIL_SIGNATURE_SEPARATOR,
    MAX_EMAIL_SIGNATURE_CHARS,
    get_email_signature_profile,
    get_email_signature_text,
    normalize_email_signature_text,
    render_email_with_signature,
    set_email_signature_text,
)


class _ScalarResult:
    """Minimal SQLAlchemy-like scalar result for service-level behavior tests."""

    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        """Return the configured scalar value."""
        return self._value


class _SignatureSession:
    """Minimal async session that stores at most one signature profile."""

    def __init__(self, profile: object | None = None) -> None:
        self.profile = profile
        self.added: list[object] = []

    async def execute(self, _statement: object) -> _ScalarResult:
        """Return the current profile for a service query."""
        return _ScalarResult(self.profile)

    def add(self, value: object) -> None:
        """Capture new models and make them visible to later reads."""
        self.added.append(value)
        self.profile = value


def _profile(signature_text: str = "Name\nRole") -> EmailSignatureProfile:
    """Create an unsaved signature profile with deterministic owner scope."""
    return EmailSignatureProfile(
        user_id="user-1",
        organization_id="org-1",
        signature_text=signature_text,
    )


def test_render_email_with_signature_uses_rfc3676_separator() -> None:
    """A configured signature is appended after the authored body unchanged."""
    body = "Please approve the attached plan by Friday."
    signature = "Seongho Bae\nAI Platform"

    rendered = render_email_with_signature(body, signature)

    assert rendered == (
        "Please approve the attached plan by Friday.\n\n"
        f"{EMAIL_SIGNATURE_SEPARATOR}\n"
        "Seongho Bae\nAI Platform"
    )
    assert rendered.startswith(body)


def test_render_email_with_signature_leaves_body_unchanged_when_disabled() -> None:
    """Missing or whitespace-only signatures must not alter authored content."""
    body = "Exact authored body\n"

    assert render_email_with_signature(body, None) == body
    assert render_email_with_signature(body, "  \r\n\t") == body


def test_render_email_with_signature_supports_signature_only_message() -> None:
    """An empty authored body does not create leading blank lines."""
    assert render_email_with_signature("", "Seongho") == "-- \nSeongho"


def test_normalize_email_signature_text_preserves_content_and_normalizes_lines() -> None:
    """Storage normalization removes only outer newlines and canonicalizes CRLF."""
    assert normalize_email_signature_text("  Name  \r\nRole\r\n") == "  Name  \nRole"


def test_normalize_email_signature_text_rejects_nul_and_oversize_values() -> None:
    """Control characters and unbounded signatures fail before SMTP send."""
    with pytest.raises(ValueError, match="NUL"):
        normalize_email_signature_text("Name\x00Role")

    with pytest.raises(ValueError, match="4096"):
        normalize_email_signature_text("x" * (MAX_EMAIL_SIGNATURE_CHARS + 1))


@pytest.mark.asyncio
async def test_get_email_signature_profile_returns_only_expected_model() -> None:
    """Unexpected scalar rows fail closed rather than leaking another scoped model."""
    expected = _profile()
    assert (
        await get_email_signature_profile(
            _SignatureSession(expected),  # type: ignore[arg-type]
            user_id="user-1",
            organization_id="org-1",
        )
        is expected
    )
    assert (
        await get_email_signature_profile(
            _SignatureSession(object()),  # type: ignore[arg-type]
            user_id="user-1",
            organization_id="org-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_email_signature_text_normalizes_existing_value() -> None:
    """Stored legacy line endings are normalized before outbound rendering."""
    profile = _profile("Name\r\nRole\r\n")
    assert await get_email_signature_text(
        _SignatureSession(profile),  # type: ignore[arg-type]
        user_id="user-1",
        organization_id="org-1",
    ) == "Name\nRole"
    assert (
        await get_email_signature_text(
            _SignatureSession(),  # type: ignore[arg-type]
            user_id="user-1",
            organization_id="org-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_set_email_signature_text_creates_updates_and_disables() -> None:
    """Persistence creates one scoped row and reuses it for later changes."""
    session = _SignatureSession()

    normalized = await set_email_signature_text(
        session,  # type: ignore[arg-type]
        user_id="user-1",
        organization_id="org-1",
        signature_text="Name\r\nRole\n",
    )

    assert normalized == "Name\nRole"
    assert len(session.added) == 1
    created = session.added[0]
    assert isinstance(created, EmailSignatureProfile)
    assert created.user_id == "user-1"
    assert created.organization_id == "org-1"
    assert created.signature_text == "Name\nRole"

    disabled = await set_email_signature_text(
        session,  # type: ignore[arg-type]
        user_id="user-1",
        organization_id="org-1",
        signature_text=None,
    )
    assert disabled is None
    assert created.signature_text == ""
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_set_email_signature_text_skips_empty_new_profile() -> None:
    """Disabling an absent signature does not create a meaningless database row."""
    session = _SignatureSession()

    assert (
        await set_email_signature_text(
            session,  # type: ignore[arg-type]
            user_id="user-1",
            organization_id=None,
            signature_text=" \n\t",
        )
        is None
    )
    assert session.added == []
