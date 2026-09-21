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


@pytest.mark.parametrize(
    ("locale_tag", "expected_locale"),
    (
        ("en-GB-oed", "en"),
        ("zh-min", "zh"),
        ("zh-min-nan", "zh"),
    ),
)
def test_explicit_locale_accepts_supported_primary_grandfathered_language_tags(
    locale_tag,
    expected_locale,
):
    """RFC 5646 grandfathered tags remain Language-Tag values even outside langtag ABNF."""
    assert normalize_supported_locale(locale_tag) == expected_locale


@pytest.mark.parametrize("locale_tag", ("x-private", "i-klingon", "sgn-BE-FR"))
def test_well_formed_language_tags_without_supported_primary_are_unsupported(locale_tag):
    """Well-formed private-use/irregular tags are unsupported, not syntactically invalid."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        normalize_supported_locale(locale_tag)
    assert caught.value.error_code == "ui_locale_unsupported"


@pytest.mark.parametrize("locale_tag", ("en-1901-1901", "en-oxendict-OXENDICT"))
def test_explicit_locale_rejects_duplicate_variant_subtags(locale_tag):
    """RFC 5646 validity forbids duplicate variant subtags case-insensitively."""
    with pytest.raises(UiLocalizationValidationError) as caught:
        normalize_supported_locale(locale_tag)
    assert caught.value.error_code == "ui_locale_input_invalid"


def test_duplicate_variant_spelling_inside_private_use_is_not_a_variant_duplicate():
    """Private-use subtags do not participate in the duplicate-variant validity rule."""
    assert normalize_supported_locale("en-1901-x-1901") == "en"
