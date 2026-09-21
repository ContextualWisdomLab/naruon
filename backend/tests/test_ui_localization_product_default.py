"""Runtime-boundary regression for the UI Localization Catalog product default."""

import pytest

from services.ui_localization_policy import UiLocalizationValidationError, select_ui_locale


@pytest.mark.parametrize("product_default", ([], {}))
def test_unhashable_product_default_fails_with_typed_locale_error(product_default):
    """Malformed runtime defaults never leak Python hashability errors."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        select_ui_locale(product_default=product_default)

    assert caught.value.error_code == "ui_locale_unsupported"
