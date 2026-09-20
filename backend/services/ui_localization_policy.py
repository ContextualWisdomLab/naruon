"""Pure policy primitives for Naruon's UI Localization Catalog.

This module intentionally owns no persistence, HTTP routing, browser runtime, or
machine-translation behavior. It defines the fail-closed identities and locale
selection rules that later boundaries consume after their canonical owner
prerequisites are integrated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from string import Formatter
from typing import Literal, cast

SupportedLocaleCode = Literal["ko", "en", "ja", "zh", "vi", "es", "de", "fr"]
LocaleSelectionSource = Literal[
    "persisted_preference",
    "session_preference",
    "accept_language",
    "product_default",
]
UiLocalizationValidationCode = Literal[
    "ui_locale_unsupported",
    "ui_locale_input_invalid",
    "ui_accept_language_invalid",
    "ui_screen_key_invalid",
    "ui_message_key_invalid",
    "ui_placeholder_schema_invalid",
    "ui_translation_placeholder_mismatch",
]

SUPPORTED_LOCALE_CODES: tuple[SupportedLocaleCode, ...] = (
    "ko",
    "en",
    "ja",
    "zh",
    "vi",
    "es",
    "de",
    "fr",
)
DEFAULT_LOCALE_CODE: SupportedLocaleCode = "ko"
_SUPPORTED_LOCALE_SET = frozenset(SUPPORTED_LOCALE_CODES)
_LOCALE_TAG_PATTERN = re.compile(
    r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$",
    flags=re.ASCII,
)
_SCREEN_KEY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    flags=re.ASCII,
)
_MESSAGE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", flags=re.ASCII)
_PLACEHOLDER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", flags=re.ASCII)
_ACCEPT_LANGUAGE_ITEM_PATTERN = re.compile(
    r"^(?P<range>\*|[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*)"
    r"(?:\s*;\s*q=(?P<quality>0(?:\.\d{0,3})?|1(?:\.0{0,3})?))?$",
    flags=re.ASCII,
)


class UiLocalizationValidationError(ValueError):
    """Stable typed validation failure emitted by the localization policy."""

    def __init__(self, error_code: UiLocalizationValidationCode, message: str) -> None:
        """Create a validation failure with a stable machine-readable code."""
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class UiLocaleSelection:
    """Resolved locale and the authority tier that selected it."""

    locale_code: SupportedLocaleCode
    selection_source: LocaleSelectionSource


def _reject_header_controls(value: str) -> None:
    """Reject control characters that could create an additional header line."""
    if any(character in value for character in ("\r", "\n", "\x00")):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input contains forbidden control characters",
        )


def normalize_supported_locale(locale_tag: str) -> SupportedLocaleCode:
    """Normalize a supported language tag to its release-level product language."""
    if not isinstance(locale_tag, str):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input must be a string",
        )
    candidate = locale_tag.strip()
    _reject_header_controls(candidate)
    if not candidate or not _LOCALE_TAG_PATTERN.fullmatch(candidate):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input is not a valid bounded language tag",
        )
    primary_language = candidate.split("-", 1)[0].lower()
    if primary_language not in _SUPPORTED_LOCALE_SET:
        raise UiLocalizationValidationError(
            "ui_locale_unsupported",
            "locale is not supported by this product release",
        )
    return cast(SupportedLocaleCode, primary_language)


def _accept_language_preferences(header_value: str) -> tuple[SupportedLocaleCode, ...]:
    """Return supported preferences ordered by quality and original specificity."""
    if not isinstance(header_value, str):
        raise UiLocalizationValidationError(
            "ui_accept_language_invalid",
            "Accept-Language must be a string",
        )
    candidate = header_value.strip()
    _reject_header_controls(candidate)
    if not candidate:
        return ()

    explicit_best: dict[SupportedLocaleCode, tuple[float, int]] = {}
    wildcard_best: tuple[float, int] | None = None

    for position, raw_item in enumerate(candidate.split(",")):
        item = raw_item.strip()
        match = _ACCEPT_LANGUAGE_ITEM_PATTERN.fullmatch(item)
        if match is None:
            raise UiLocalizationValidationError(
                "ui_accept_language_invalid",
                "Accept-Language contains an invalid language range or quality value",
            )
        quality = float(match.group("quality") or "1")
        language_range = match.group("range")
        if language_range == "*":
            candidate_rank = (quality, position)
            if wildcard_best is None or candidate_rank[0] > wildcard_best[0]:
                wildcard_best = candidate_rank
            continue

        primary_language = language_range.split("-", 1)[0].lower()
        if primary_language not in _SUPPORTED_LOCALE_SET:
            continue
        locale_code = cast(SupportedLocaleCode, primary_language)
        current = explicit_best.get(locale_code)
        if current is None or quality > current[0]:
            explicit_best[locale_code] = (quality, position)

    ranked: list[tuple[float, int, int, SupportedLocaleCode]] = []
    for release_order, locale_code in enumerate(SUPPORTED_LOCALE_CODES):
        explicit_rank = explicit_best.get(locale_code)
        if explicit_rank is not None:
            quality, position = explicit_rank
        elif wildcard_best is not None:
            quality, position = wildcard_best
        else:
            continue
        if quality == 0:
            continue
        ranked.append((quality, position, release_order, locale_code))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return tuple(item[3] for item in ranked)


def select_ui_locale(
    *,
    persisted_preference: str | None = None,
    session_preference: str | None = None,
    accept_language: str | None = None,
    product_default: SupportedLocaleCode = DEFAULT_LOCALE_CODE,
) -> UiLocaleSelection:
    """Resolve one supported locale using the product's explicit authority order."""
    if product_default not in _SUPPORTED_LOCALE_SET:
        raise UiLocalizationValidationError(
            "ui_locale_unsupported",
            "product default locale must be supported",
        )
    if persisted_preference is not None:
        return UiLocaleSelection(
            normalize_supported_locale(persisted_preference),
            "persisted_preference",
        )
    if session_preference is not None:
        return UiLocaleSelection(
            normalize_supported_locale(session_preference),
            "session_preference",
        )
    if accept_language is not None:
        preferences = _accept_language_preferences(accept_language)
        if preferences:
            return UiLocaleSelection(preferences[0], "accept_language")
    return UiLocaleSelection(product_default, "product_default")


def validate_screen_key(screen_key: str) -> str:
    """Return a normalized screen identity or fail closed on invalid input."""
    if not isinstance(screen_key, str) or not _SCREEN_KEY_PATTERN.fullmatch(screen_key):
        raise UiLocalizationValidationError(
            "ui_screen_key_invalid",
            "screen_key must be a dotted lowercase product identity",
        )
    return screen_key


def validate_message_key(message_key: str) -> str:
    """Return a normalized message identity or fail closed on invalid input."""
    if not isinstance(message_key, str) or not _MESSAGE_KEY_PATTERN.fullmatch(message_key):
        raise UiLocalizationValidationError(
            "ui_message_key_invalid",
            "message_key must be lowercase snake_case",
        )
    return message_key


def extract_placeholder_names(message_text: str) -> tuple[str, ...]:
    """Extract simple named interpolation fields without evaluating the message."""
    if not isinstance(message_text, str):
        raise UiLocalizationValidationError(
            "ui_placeholder_schema_invalid",
            "translated message must be a string",
        )
    names: list[str] = []
    seen: set[str] = set()
    try:
        parsed = Formatter().parse(message_text)
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if (
                not _PLACEHOLDER_NAME_PATTERN.fullmatch(field_name)
                or format_spec
                or conversion is not None
            ):
                raise UiLocalizationValidationError(
                    "ui_placeholder_schema_invalid",
                    "placeholders must be simple named fields without conversion or format specifiers",
                )
            if field_name not in seen:
                seen.add(field_name)
                names.append(field_name)
    except ValueError as error:
        raise UiLocalizationValidationError(
            "ui_placeholder_schema_invalid",
            "message contains malformed placeholder syntax",
        ) from error
    return tuple(names)


def validate_translation_placeholders(
    translated_message: str,
    placeholder_schema: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Require the translated message to preserve the exact placeholder schema."""
    schema = tuple(placeholder_schema)
    if len(schema) != len(set(schema)) or any(
        not isinstance(name, str) or not _PLACEHOLDER_NAME_PATTERN.fullmatch(name)
        for name in schema
    ):
        raise UiLocalizationValidationError(
            "ui_placeholder_schema_invalid",
            "placeholder schema must contain unique lowercase snake_case names",
        )
    actual = extract_placeholder_names(translated_message)
    if set(actual) != set(schema):
        raise UiLocalizationValidationError(
            "ui_translation_placeholder_mismatch",
            "translated message placeholders do not match the versioned schema",
        )
    return actual
