"""Behavior contracts for scoped plain-text outbound email signatures."""

from __future__ import annotations

import pytest

from services.email_signature_service import (
    EMAIL_SIGNATURE_SEPARATOR,
    MAX_EMAIL_SIGNATURE_CHARS,
    normalize_email_signature_text,
    render_email_with_signature,
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
