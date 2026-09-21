"""Resource-bound regressions for translation text and placeholder metadata."""

import pytest

from services.ui_localization_policy import (
    UiLocalizationValidationError,
    extract_placeholder_names,
    validate_translation_placeholders,
)


def assert_error(code, callable_):
    """Assert one stable localization validation code from a failing call."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        callable_()
    assert caught.value.error_code == code


def test_translation_text_character_budget_is_bounded_before_placeholder_work():
    """UI copy accepts 16,384 characters and rejects the next character without truncation."""
    assert extract_placeholder_names("가" * 16_384) == ()
    assert_error(
        "ui_translation_input_invalid",
        lambda: extract_placeholder_names("가" * 16_385),
    )


def test_placeholder_name_character_budget_is_bounded():
    """Versioned placeholder identities accept 64 characters and reject the 65th."""
    accepted_name = "a" + ("b" * 63)
    rejected_name = accepted_name + "c"

    assert validate_translation_placeholders(
        "{" + accepted_name + "}",
        (accepted_name,),
    ) == (accepted_name,)
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders(
            "{" + rejected_name + "}",
            (rejected_name,),
        ),
    )


def test_placeholder_schema_item_budget_is_bounded_before_collection_copy():
    """A catalog message accepts 32 unique placeholders and rejects the 33rd."""
    accepted_schema = tuple(f"field_{index}" for index in range(32))
    accepted_message = " ".join(f"{{{name}}}" for name in accepted_schema)
    rejected_schema = (*accepted_schema, "field_32")
    rejected_message = accepted_message + " {field_32}"

    assert validate_translation_placeholders(
        accepted_message,
        accepted_schema,
    ) == accepted_schema
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders(
            rejected_message,
            rejected_schema,
        ),
    )
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: extract_placeholder_names(rejected_message),
    )
