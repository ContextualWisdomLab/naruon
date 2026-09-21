"""BCP 47 well-formedness regressions for explicit locale preferences."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    normalize_supported_locale,
)


@pytest.mark.parametrize("locale_tag", ("en-x", "en-u"))
def test_explicit_locale_rejects_terminal_extension_or_private_use_singletons(locale_tag):
    """A supported primary language does not make a malformed RFC 5646 suffix valid."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        normalize_supported_locale(locale_tag)
    assert caught.value.error_code == "ui_locale_input_invalid"


@pytest.mark.parametrize("locale_tag", ("en-x-private", "en-u-ca-gregory"))
def test_explicit_locale_accepts_well_formed_private_use_and_extension_suffixes(locale_tag):
    """Valid RFC 5646 suffixes remain compatible with release-level locale normalization."""
    assert normalize_supported_locale(locale_tag) == "en"
