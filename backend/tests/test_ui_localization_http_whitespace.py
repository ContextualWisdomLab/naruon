"""HTTP/locale whitespace regressions for the UI Localization Catalog policy."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    normalize_supported_locale,
    select_ui_locale,
)


def assert_error(code, callable_):
    """Assert a stable localization validation code from one failing call."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        callable_()
    assert caught.value.error_code == code


@pytest.mark.parametrize(
    "locale_tag",
    (
        "\ten-US",
        "en-US\v",
        "\fen-US",
        "\u00a0en-US",
    ),
)
def test_explicit_locale_rejects_non_space_boundary_whitespace(locale_tag):
    """Only ASCII SP is benign outer whitespace for stored/session locale values."""
    assert_error("ui_locale_input_invalid", lambda: normalize_supported_locale(locale_tag))


@pytest.mark.parametrize(
    "header_value",
    (
        "\ven-US",
        "en-US\f",
        "en-US\v;q=0.8",
        "en-US;\fq=0.8",
        "\u00a0en-US",
    ),
)
def test_accept_language_rejects_non_http_whitespace(header_value):
    """VT, FF, and Unicode whitespace are not RFC 9110 OWS and fail closed."""
    assert_error(
        "ui_accept_language_invalid",
        lambda: select_ui_locale(accept_language=header_value),
    )


def test_accept_language_allows_only_sp_and_htab_as_ows():
    """RFC 9110 OWS remains accepted around list members and q-weights."""
    selected = select_ui_locale(accept_language="\ten-US\t,\tfr ;\tq=0.5\t")
    assert (selected.locale_code, selected.selection_source) == ("en", "accept_language")


def test_accept_language_quality_parameter_name_is_case_insensitive():
    """RFC 9110 defines the q parameter name as case-insensitive."""
    selected = select_ui_locale(accept_language="fr;Q=0.4, en;q=0.8")
    assert (selected.locale_code, selected.selection_source) == ("en", "accept_language")

    selected = select_ui_locale(accept_language="fr;Q=0.9, en;q=0.8")
    assert (selected.locale_code, selected.selection_source) == ("fr", "accept_language")


def test_accept_language_ignores_reasonable_empty_list_elements():
    """RFC 9110 recipients ignore empty members introduced while list values are merged."""
    selected = select_ui_locale(accept_language=", fr;q=0.4, , en;q=0.8,")
    assert (selected.locale_code, selected.selection_source) == ("en", "accept_language")

    selected = select_ui_locale(accept_language=",")
    assert (selected.locale_code, selected.selection_source) == ("ko", "product_default")
