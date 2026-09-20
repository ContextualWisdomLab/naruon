"""Translation-text boundary regressions for the UI Localization Catalog policy."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    extract_placeholder_names,
    validate_translation_placeholders,
)


def assert_error(code, callable_):
    """Assert a stable localization validation code from one failing call."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        callable_()
    assert caught.value.error_code == code


@pytest.mark.parametrize(
    "message_text",
    (
        "\x00{name}",
        "{name}\x00",
        "\ud800{name}",
        "{name}\udfff",
    ),
)
def test_translation_text_rejects_non_persistable_unicode(message_text):
    """NUL and surrogate code points fail at the translation boundary before publication."""
    assert_error(
        "ui_translation_input_invalid",
        lambda: validate_translation_placeholders(message_text, ("name",)),
    )


def test_non_string_translation_text_keeps_translation_boundary_identity():
    """A non-string translation reports the translation boundary, not a schema failure."""
    assert_error("ui_translation_input_invalid", lambda: extract_placeholder_names(None))


def test_translation_text_allows_normal_multiline_unicode():
    """The boundary does not reject ordinary Unicode, newlines, or tabs used by UI copy."""
    assert validate_translation_placeholders(
        "안녕하세요, {name}님.\n\t다음 일정이 있습니다.",
        ("name",),
    ) == ("name",)
