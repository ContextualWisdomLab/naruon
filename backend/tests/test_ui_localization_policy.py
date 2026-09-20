"""Regression coverage for the UI Localization Catalog domain policy."""

import pytest

from services.ui_localization_policy import (
    SUPPORTED_LOCALE_CODES,
    UiLocalizationValidationError,
    extract_placeholder_names,
    normalize_supported_locale,
    select_ui_locale,
    validate_message_key,
    validate_screen_key,
    validate_translation_placeholders,
)


def assert_error(code, callable_):
    """Assert a stable localization validation code from one failing call."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        callable_()
    assert caught.value.error_code == code


def test_supported_release_locales_are_fixed():
    """The first catalog release is exactly the eight product languages."""
    assert SUPPORTED_LOCALE_CODES == ("ko", "en", "ja", "zh", "vi", "es", "de", "fr")


def test_locale_normalization_preserves_supported_primary_language():
    """Supported regional and script variants resolve to the release language."""
    assert normalize_supported_locale("ko-KR") == "ko"
    assert normalize_supported_locale("zh-Hant-TW") == "zh"
    assert normalize_supported_locale("FR-fr") == "fr"


def test_explicit_unsupported_or_invalid_locale_fails_closed():
    """Explicit preferences never silently turn into a different locale."""
    assert_error("ui_locale_unsupported", lambda: normalize_supported_locale("pt-BR"))
    assert_error("ui_locale_input_invalid", lambda: normalize_supported_locale("en_US"))
    assert_error(
        "ui_locale_input_invalid",
        lambda: normalize_supported_locale("en\r\nX-Test: bad"),
    )


@pytest.mark.parametrize("locale_tag", ("\r\nen-US", "en-US\r\n"))
def test_locale_normalization_rejects_edge_crlf_before_trimming(locale_tag):
    """CR/LF at either edge is rejected rather than normalized away by whitespace trimming."""
    assert_error("ui_locale_input_invalid", lambda: normalize_supported_locale(locale_tag))


def test_selection_precedence_is_persisted_session_accept_language_default():
    """Locale authority follows the catalog contract in descending precedence."""
    selected = select_ui_locale(
        persisted_preference="de-DE",
        session_preference="fr-FR",
        accept_language="es;q=1.0",
    )
    assert (selected.locale_code, selected.selection_source) == ("de", "persisted_preference")

    selected = select_ui_locale(session_preference="fr-FR", accept_language="es;q=1.0")
    assert (selected.locale_code, selected.selection_source) == ("fr", "session_preference")

    selected = select_ui_locale(accept_language="es-MX;q=0.7, ja-JP;q=0.9")
    assert (selected.locale_code, selected.selection_source) == ("ja", "accept_language")

    selected = select_ui_locale(accept_language="pt-BR, it;q=0.7")
    assert (selected.locale_code, selected.selection_source) == ("ko", "product_default")


def test_accept_language_duplicate_quality_is_not_first_occurrence_biased():
    """A later duplicate with higher quality outranks lower-quality peers."""
    selected = select_ui_locale(
        accept_language="fr;q=0.7, fr-FR;q=0.9, fr-CA;q=0.6, en;q=0.8"
    )
    assert selected.locale_code == "fr"


def test_accept_language_zero_quality_and_wildcard_follow_lookup_order():
    """Wildcard lookup defers to a later concrete range and q=0 stays excluded."""
    selected = select_ui_locale(accept_language="ko;q=0, *;q=0.8, en;q=0.7")
    assert selected.locale_code == "en"
    selected = select_ui_locale(accept_language="fr;q=0, *;q=0")
    assert selected.locale_code == "ko"


def test_wildcard_lookup_skips_to_later_concrete_range():
    """RFC 4647 lookup skips wildcard when a later concrete range can be tried."""
    selected = select_ui_locale(accept_language="en;q=0.9, *;q=0.8, fr;q=0.7")
    assert selected.locale_code == "en"
    selected = select_ui_locale(accept_language="*;q=0.7, *;q=0.9, *;q=0.5, fr;q=0.8")
    assert selected.locale_code == "fr"
    selected = select_ui_locale(accept_language="*;q=0.9")
    assert selected.locale_code == "ko"


def test_malformed_accept_language_fails_closed():
    """Malformed quality values and header injection do not fall through to defaults."""
    assert_error(
        "ui_accept_language_invalid",
        lambda: select_ui_locale(accept_language="en;q=1.2"),
    )
    assert_error(
        "ui_accept_language_invalid",
        lambda: select_ui_locale(accept_language="en\r\nX-Test: bad"),
    )


@pytest.mark.parametrize("header_value", ("\r\nen-US", "en-US\r\n"))
def test_accept_language_rejects_edge_crlf_before_trimming(header_value):
    """Header-edge CR/LF cannot disappear before the injection guard runs."""
    assert_error(
        "ui_accept_language_invalid",
        lambda: select_ui_locale(accept_language=header_value),
    )


def test_non_string_locale_inputs_fail_closed():
    """Non-string boundary values produce typed validation failures."""
    assert_error("ui_locale_input_invalid", lambda: normalize_supported_locale(None))
    assert_error("ui_accept_language_invalid", lambda: select_ui_locale(accept_language=42))


def test_empty_accept_language_and_no_header_use_default():
    """An absent effective negotiation result uses the configured product default."""
    selected = select_ui_locale(accept_language="   ")
    assert (selected.locale_code, selected.selection_source) == ("ko", "product_default")
    selected = select_ui_locale()
    assert (selected.locale_code, selected.selection_source) == ("ko", "product_default")


def test_custom_supported_default_and_invalid_default():
    """Deployments may choose another supported default but never an unsupported one."""
    selected = select_ui_locale(accept_language="it", product_default="fr")
    assert selected.locale_code == "fr"
    assert_error(
        "ui_locale_unsupported",
        lambda: select_ui_locale(product_default="pt"),
    )


def test_screen_and_message_identities_are_bounded():
    """Catalog identifiers stay within stable product-key syntax."""
    assert validate_screen_key("settings.identity") == "settings.identity"
    assert validate_message_key("oidc_login_pending") == "oidc_login_pending"
    assert_error("ui_screen_key_invalid", lambda: validate_screen_key("settings"))
    assert_error("ui_screen_key_invalid", lambda: validate_screen_key("../settings.identity"))
    assert_error("ui_message_key_invalid", lambda: validate_message_key("OIDC.Login"))


def test_non_string_and_invalid_identity_inputs_fail_closed():
    """Non-string and non-snake-case identities are rejected before persistence."""
    assert_error("ui_screen_key_invalid", lambda: validate_screen_key(None))
    assert_error("ui_message_key_invalid", lambda: validate_message_key(None))
    assert_error("ui_message_key_invalid", lambda: validate_message_key("oidc-login"))


def test_placeholder_extraction_is_literal_and_ordered():
    """Interpolation fields are inspected without evaluating format expressions."""
    assert extract_placeholder_names("{account_name}님, {count}건 / {account_name}") == (
        "account_name",
        "count",
    )
    assert extract_placeholder_names("{{literal}}") == ()


def test_placeholder_schema_rejects_missing_extra_and_formatter_features():
    """Translations preserve the exact schema and reject formatter field traversal."""
    assert validate_translation_placeholders(
        "{count}개의 알림이 {account_name}님에게 있습니다.",
        ("account_name", "count"),
    ) == ("count", "account_name")
    assert_error(
        "ui_translation_placeholder_mismatch",
        lambda: validate_translation_placeholders(
            "{account_name}님",
            ("account_name", "count"),
        ),
    )
    assert_error(
        "ui_translation_placeholder_mismatch",
        lambda: validate_translation_placeholders("{account_name}님 {extra}", ("account_name",)),
    )
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders("{account_name.value}", ("account_name",)),
    )
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders("{count:03d}", ("count",)),
    )
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders("{account_name!r}", ("account_name",)),
    )


def test_placeholder_input_and_schema_must_be_bounded():
    """Malformed text, duplicates, and invalid schema names fail before publication."""
    assert_error("ui_placeholder_schema_invalid", lambda: extract_placeholder_names(None))
    assert_error("ui_placeholder_schema_invalid", lambda: extract_placeholder_names("{missing"))
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders("{name}", ("name", "name")),
    )
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders("{name}", ("Name",)),
    )
    assert_error(
        "ui_placeholder_schema_invalid",
        lambda: validate_translation_placeholders("{name}", (None,)),
    )
