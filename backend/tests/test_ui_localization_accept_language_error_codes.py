"""Regression coverage for typed Accept-Language control-character failures."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    normalize_supported_locale,
    select_ui_locale,
)


def test_accept_language_controls_report_header_validation_code():
    """Header injection syntax stays distinguishable from explicit locale input."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        select_ui_locale(accept_language="en\r\nX-Test: bad")

    assert caught.value.error_code == "ui_accept_language_invalid"


def test_explicit_locale_controls_keep_locale_validation_code():
    """The same control characters retain the explicit-locale boundary code."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        normalize_supported_locale("en\r\nX-Test: bad")

    assert caught.value.error_code == "ui_locale_input_invalid"
