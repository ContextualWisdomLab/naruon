"""Regression tests for canonical CardDAV TXT context-path execution."""

from services.carddav_discovery import _txt_context_path


def test_fully_encoded_leading_slash_is_canonicalized() -> None:
    """Execute the same decoded representation that passed validation."""
    assert _txt_context_path(["path=%2Fsafe"]) == "/safe"


def test_percent_encoded_unicode_path_is_canonicalized() -> None:
    """Preserve a safe Unicode path after bounded decoding."""
    assert _txt_context_path(["path=/%EC%A3%BC%EC%86%8C%EB%A1%9D"]) == "/주소록"
