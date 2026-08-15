"""Focused boundary tests for runtime encryption key identifiers."""

import pytest

from core.runtime_secrets import validate_encryption_key_id


def test_validate_encryption_key_id_accepts_documented_character_set_and_boundary():
    """Accept normalized identifiers through the 64-character upper bound."""
    assert validate_encryption_key_id("TEST_SETTING", "primary") == "primary"
    assert validate_encryption_key_id("TEST_SETTING", "key-1") == "key-1"
    assert validate_encryption_key_id("TEST_SETTING", "key_2") == "key_2"
    assert validate_encryption_key_id("TEST_SETTING", "KEY.3") == "KEY.3"
    assert (
        validate_encryption_key_id("TEST_SETTING", "  key-with-spaces  ")
        == "key-with-spaces"
    )
    assert validate_encryption_key_id("TEST_SETTING", "a" * 64) == "a" * 64


@pytest.mark.parametrize(
    "key_id",
    [
        "",
        "   ",
        "-key",
        ".key",
        "_key",
        "key!",
        "key@name",
        "a" * 65,
    ],
)
def test_validate_encryption_key_id_rejects_invalid_format_and_length(key_id: str):
    """Reject invalid leading punctuation, characters, emptiness, and overflow."""
    with pytest.raises(RuntimeError, match="TEST_SETTING must be 1-64 characters"):
        validate_encryption_key_id("TEST_SETTING", key_id)
