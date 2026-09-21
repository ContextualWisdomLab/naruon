"""RFC 5646 extension-singleton regressions for explicit locale preferences."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    normalize_supported_locale,
)


@pytest.mark.parametrize("locale_tag", ("en-a-bbb-a-ccc", "EN-A-bbb-a-ccc"))
def test_explicit_locale_rejects_repeated_extension_singleton(locale_tag):
    """RFC 5646 forbids repeating an extension singleton outside private use."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        normalize_supported_locale(locale_tag)
    assert caught.value.error_code == "ui_locale_input_invalid"


def test_private_use_may_repeat_extension_letter_after_x():
    """Singleton-shaped private-use data is not a repeated extension singleton."""
    assert normalize_supported_locale("en-a-bbb-x-a-ccc") == "en"
