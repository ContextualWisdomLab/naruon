"""Scope-safe persistence and rendering for plain-text outbound signatures."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.email_signature_models import EmailSignatureProfile

EMAIL_SIGNATURE_SEPARATOR = "-- "
MAX_EMAIL_SIGNATURE_CHARS = 4096


def normalize_email_signature_text(signature_text: str | None) -> str | None:
    """Validate and normalize a user-authored plain-text signature.

    CRLF and legacy CR line endings are normalized to LF for deterministic
    storage. Leading spaces are preserved because signatures commonly use
    intentional indentation; only outer line breaks are removed. A blank
    signature disables automatic insertion.

    Args:
        signature_text: User-authored signature text, or ``None`` to disable it.

    Returns:
        Normalized signature text, or ``None`` when the value is disabled.

    Raises:
        ValueError: If the signature contains NUL or exceeds the bounded size.
    """
    if signature_text is None:
        return None
    if "\x00" in signature_text:
        raise ValueError("Email signature must not contain NUL characters")
    if len(signature_text) > MAX_EMAIL_SIGNATURE_CHARS:
        raise ValueError(
            f"Email signature must not exceed {MAX_EMAIL_SIGNATURE_CHARS} characters"
        )

    normalized = signature_text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return normalized if normalized.strip() else None


def render_email_with_signature(body: str, signature_text: str | None) -> str:
    """Append one RFC 3676-style separator and configured plain-text signature.

    The authored body is preserved byte-for-byte as a prefix. The function
    does not guess whether user prose resembles a signature; disabling the
    configured signature is the only way to omit automatic insertion.
    """
    signature = normalize_email_signature_text(signature_text)
    if signature is None:
        return body
    signature_block = f"{EMAIL_SIGNATURE_SEPARATOR}\n{signature}"
    if not body:
        return signature_block
    return f"{body}\n\n{signature_block}"


async def get_email_signature_profile(
    db: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
) -> EmailSignatureProfile | None:
    """Return the signature profile for one authenticated mailbox scope."""
    result = await db.execute(
        select(EmailSignatureProfile).where(
            EmailSignatureProfile.user_id == user_id,
            EmailSignatureProfile.organization_id == organization_id,
        )
    )
    profile = result.scalar_one_or_none()
    return profile if isinstance(profile, EmailSignatureProfile) else None


async def get_email_signature_text(
    db: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
) -> str | None:
    """Return normalized signature text for one authenticated mailbox scope."""
    profile = await get_email_signature_profile(
        db,
        user_id=user_id,
        organization_id=organization_id,
    )
    if profile is None:
        return None
    return normalize_email_signature_text(profile.signature_text)


async def set_email_signature_text(
    db: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
    signature_text: str | None,
) -> str | None:
    """Create or update the normalized signature within one mailbox scope.

    The caller owns the surrounding transaction so mailbox configuration and
    signature changes can be committed atomically.
    """
    normalized = normalize_email_signature_text(signature_text)
    profile = await get_email_signature_profile(
        db,
        user_id=user_id,
        organization_id=organization_id,
    )
    if profile is None:
        if normalized is None:
            return None
        profile = EmailSignatureProfile(
            user_id=user_id,
            organization_id=organization_id,
            signature_text=normalized,
        )
        db.add(profile)
    else:
        profile.signature_text = normalized or ""
    return normalized
