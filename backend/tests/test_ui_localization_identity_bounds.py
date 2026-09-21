"""Resource-bound regressions for UI Localization Catalog identities."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    validate_message_key,
    validate_screen_key,
)


def assert_error(code, callable_):
    """Assert a stable localization validation code from one failing call."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        callable_()
    assert caught.value.error_code == code


def test_screen_key_has_explicit_product_length_bound():
    """A syntactically valid screen identity cannot create unbounded catalog/index work."""
    screen_key_at_limit = "a." + ("b" * 126)
    assert len(screen_key_at_limit) == 128
    assert validate_screen_key(screen_key_at_limit) == screen_key_at_limit

    screen_key_over_limit = screen_key_at_limit + "b"
    assert_error(
        "ui_screen_key_invalid",
        lambda: validate_screen_key(screen_key_over_limit),
    )


def test_message_key_has_explicit_product_length_bound():
    """A syntactically valid message identity cannot grow without a product ceiling."""
    message_key_at_limit = "m" * 128
    assert validate_message_key(message_key_at_limit) == message_key_at_limit

    message_key_over_limit = message_key_at_limit + "m"
    assert_error(
        "ui_message_key_invalid",
        lambda: validate_message_key(message_key_over_limit),
    )
