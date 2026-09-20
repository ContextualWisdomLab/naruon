"""Regression coverage for Accept-Language wildcard fallback exclusions."""

from services.ui_localization_policy import select_ui_locale


def test_wildcard_fallback_does_not_return_explicit_q_zero_default():
    """A wildcard keeps unspecified locales acceptable without reviving q=0."""
    selected = select_ui_locale(accept_language="ko;q=0, *;q=0.8")

    assert selected.locale_code == "en"
    assert selected.selection_source == "accept_language"
