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
    "ui_translation_input_invalid",
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
_MAX_LOCALE_TAG_CHARS = 128
_MAX_ACCEPT_LANGUAGE_CHARS = 8192
_MAX_ACCEPT_LANGUAGE_MEMBERS = 64
_MAX_ACCEPT_LANGUAGE_EMPTY_MEMBERS = 32
_MAX_SCREEN_KEY_CHARS = 128
_MAX_MESSAGE_KEY_CHARS = 128
_MAX_TRANSLATION_MESSAGE_CHARS = 16_384
_MAX_PLACEHOLDER_NAME_CHARS = 64
_MAX_PLACEHOLDER_SCHEMA_ITEMS = 32
_LANGTAG_PATTERN = re.compile(
    r"^(?:[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})"
    r"(?:-[A-Za-z]{4})?"
    r"(?:-(?:[A-Za-z]{2}|[0-9]{3}))?"
    r"(?:-(?:[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*"
    r"(?:-[0-9A-WY-Za-wy-z](?:-[A-Za-z0-9]{2,8})+)*"
    r"(?:-[xX](?:-[A-Za-z0-9]{1,8})+)?$",
    flags=re.ASCII | re.IGNORECASE,
)
_PRIVATEUSE_TAG_PATTERN = re.compile(
    r"^[xX](?:-[A-Za-z0-9]{1,8})+$",
    flags=re.ASCII,
)
_IRREGULAR_GRANDFATHERED_TAGS = frozenset(
    tag.lower()
    for tag in (
        "en-GB-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "sgn-BE-FR",
        "sgn-BE-NL",
        "sgn-CH-DE",
        "zh-min",
        "zh-min-nan",
    )
)
_SCREEN_KEY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    flags=re.ASCII,
)
_MESSAGE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", flags=re.ASCII)
_PLACEHOLDER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", flags=re.ASCII)
_ACCEPT_LANGUAGE_ITEM_PATTERN = re.compile(
    r"^(?P<range>\*|[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*)"
    r"(?:[ \t]*;[ \t]*[qQ]=(?P<quality>0(?:\.\d{0,3})?|1(?:\.0{0,3})?))?$",
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


def _reject_control_characters(
    value: str,
    *,
    error_code: UiLocalizationValidationCode,
    message: str,
    allow_horizontal_tab: bool = False,
) -> None:
    """Reject C0/DEL controls while preserving the caller's boundary code."""
    for character in value:
        code_point = ord(character)
        if code_point == 0x7F or (
            code_point < 0x20 and not (allow_horizontal_tab and character == "\t")
        ):
            raise UiLocalizationValidationError(error_code, message)


def _has_repeated_extension_singleton(locale_tag: str) -> bool:
    """Return whether a structural langtag repeats an extension singleton before private use."""
    seen_singletons: set[str] = set()
    for subtag in locale_tag.split("-")[1:]:
        normalized = subtag.lower()
        if normalized == "x":
            break
        if len(subtag) != 1:
            continue
        if normalized in seen_singletons:
            return True
        seen_singletons.add(normalized)
    return False


def _has_multiple_extlang_subtags(locale_tag: str) -> bool:
    """Return whether a structural langtag occupies a reserved second extlang position."""
    subtags = locale_tag.split("-")
    if len(subtags[0]) not in (2, 3):
        return False
    extlang_count = 0
    for subtag in subtags[1:4]:
        if len(subtag) != 3 or not subtag.isalpha():
            break
        extlang_count += 1
    return extlang_count > 1


def _has_repeated_variant_subtag(locale_tag: str) -> bool:
    """Return whether a structural langtag repeats a variant before extensions/private use."""
    subtags = locale_tag.split("-")
    index = 1
    primary_language = subtags[0]

    if len(primary_language) in (2, 3):
        extlang_count = 0
        while (
            index < len(subtags)
            and extlang_count < 3
            and len(subtags[index]) == 3
            and subtags[index].isalpha()
        ):
            index += 1
            extlang_count += 1

    if index < len(subtags) and len(subtags[index]) == 4 and subtags[index].isalpha():
        index += 1

    if index < len(subtags) and (
        (len(subtags[index]) == 2 and subtags[index].isalpha())
        or (len(subtags[index]) == 3 and subtags[index].isdigit())
    ):
        index += 1

    seen_variants: set[str] = set()
    while index < len(subtags):
        subtag = subtags[index]
        if len(subtag) == 1:
            break
        is_variant = (5 <= len(subtag) <= 8 and subtag.isalnum()) or (
            len(subtag) == 4 and subtag[0].isdigit() and subtag[1:].isalnum()
        )
        if not is_variant:
            break
        normalized = subtag.lower()
        if normalized in seen_variants:
            return True
        seen_variants.add(normalized)
        index += 1
    return False


def normalize_supported_locale(locale_tag: str) -> SupportedLocaleCode:
    """Normalize a supported language tag to its release-level product language."""
    if not isinstance(locale_tag, str):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input must be a string",
        )
    if len(locale_tag) > _MAX_LOCALE_TAG_CHARS:
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input exceeds the 128-character product limit",
        )
    _reject_control_characters(
        locale_tag,
        error_code="ui_locale_input_invalid",
        message="locale input contains forbidden control characters",
    )
    candidate = locale_tag.strip(" ")
    candidate_lower = candidate.lower()
    is_structural_langtag = _LANGTAG_PATTERN.fullmatch(candidate) is not None
    if is_structural_langtag and _has_multiple_extlang_subtags(candidate):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input contains more than one RFC 5646 extended language subtag",
        )
    if is_structural_langtag and _has_repeated_extension_singleton(candidate):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input repeats an RFC 5646 extension singleton",
        )
    if is_structural_langtag and _has_repeated_variant_subtag(candidate):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input repeats an RFC 5646 variant subtag",
        )
    if not candidate or not (
        is_structural_langtag
        or _PRIVATEUSE_TAG_PATTERN.fullmatch(candidate)
        or candidate_lower in _IRREGULAR_GRANDFATHERED_TAGS
    ):
        raise UiLocalizationValidationError(
            "ui_locale_input_invalid",
            "locale input is not a well-formed bounded RFC 5646 language tag",
        )
    primary_language = candidate.split("-", 1)[0].lower()
    if primary_language not in _SUPPORTED_LOCALE_SET:
        raise UiLocalizationValidationError(
            "ui_locale_unsupported",
            "locale is not supported by this product release",
        )
    return cast(SupportedLocaleCode, primary_language)


def _accept_language_preferences(
    header_value: str,
    product_default: SupportedLocaleCode,
) -> tuple[SupportedLocaleCode, ...]:
    """Return supported preferences using weighted RFC 4647 lookup ordering."""
    if not isinstance(header_value, str):
        raise UiLocalizationValidationError(
            "ui_accept_language_invalid",
            "Accept-Language must be a string",
        )
    if len(header_value) > _MAX_ACCEPT_LANGUAGE_CHARS:
        raise UiLocalizationValidationError(
            "ui_accept_language_invalid",
            "Accept-Language exceeds the 8192-character product limit",
        )
    _reject_control_characters(
        header_value,
        error_code="ui_accept_language_invalid",
        message="Accept-Language contains forbidden control characters",
        allow_horizontal_tab=True,
    )
    candidate = header_value.strip(" \t")
    if not candidate:
        return ()

    explicit_best: dict[SupportedLocaleCode, tuple[float, int]] = {}
    concrete_priorities: list[tuple[float, int]] = []
    wildcard_best: tuple[float, int] | None = None
    non_empty_members = 0
    empty_members = 0

    for position, raw_item in enumerate(candidate.split(",")):
        item = raw_item.strip(" \t")
        if not item:
            empty_members += 1
            if empty_members > _MAX_ACCEPT_LANGUAGE_EMPTY_MEMBERS:
                raise UiLocalizationValidationError(
                    "ui_accept_language_invalid",
                    "Accept-Language contains too many empty list members",
                )
            continue
        non_empty_members += 1
        if non_empty_members > _MAX_ACCEPT_LANGUAGE_MEMBERS:
            raise UiLocalizationValidationError(
                "ui_accept_language_invalid",
                "Accept-Language contains too many language ranges",
            )
        match = _ACCEPT_LANGUAGE_ITEM_PATTERN.fullmatch(item)
        if match is None:
            raise UiLocalizationValidationError(
                "ui_accept_language_invalid",
                "Accept-Language contains an invalid language range or quality value",
            )
        quality = float(match.group("quality") or "1")
        language_range = match.group("range")
        if language_range == "*":
            if wildcard_best is None or quality > wildcard_best[0]:
                wildcard_best = (quality, position)
            continue

        if quality > 0:
            concrete_priorities.append((quality, position))
        primary_language = language_range.split("-", 1)[0].lower()
        if primary_language not in _SUPPORTED_LOCALE_SET:
            continue
        locale_code = cast(SupportedLocaleCode, primary_language)
        current = explicit_best.get(locale_code)
        if current is None or quality > current[0]:
            explicit_best[locale_code] = (quality, position)

    ranked: list[tuple[float, int, SupportedLocaleCode | None]] = [
        (quality, position, locale_code)
        for locale_code, (quality, position) in explicit_best.items()
        if quality > 0
    ]
    if wildcard_best is not None and wildcard_best[0] > 0:
        ranked.append((wildcard_best[0], wildcard_best[1], None))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    excluded_locales = {
        locale_code
        for locale_code, (quality, _) in explicit_best.items()
        if quality == 0
    }
    ordered: list[SupportedLocaleCode] = []
    for quality, position, locale_code in ranked:
        if locale_code is None:
            wildcard_priority = (-quality, position)
            if any(
                (-concrete_quality, concrete_position) > wildcard_priority
                for concrete_quality, concrete_position in concrete_priorities
            ):
                continue
            if not excluded_locales:
                break
            wildcard_candidates = (product_default, *SUPPORTED_LOCALE_CODES)
            for wildcard_candidate in wildcard_candidates:
                if (
                    wildcard_candidate not in excluded_locales
                    and wildcard_candidate not in ordered
                ):
                    ordered.append(wildcard_candidate)
                    break
            break
        ordered.append(locale_code)
    return tuple(ordered)


def select_ui_locale(
    *,
    persisted_preference: str | None = None,
    session_preference: str | None = None,
    accept_language: str | None = None,
    product_default: SupportedLocaleCode = DEFAULT_LOCALE_CODE,
) -> UiLocaleSelection:
    """Resolve one supported locale using the product's explicit authority order."""
    if not isinstance(product_default, str) or product_default not in _SUPPORTED_LOCALE_SET:
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
        preferences = _accept_language_preferences(accept_language, product_default)
        if preferences:
            return UiLocaleSelection(preferences[0], "accept_language")
    return UiLocaleSelection(product_default, "product_default")


def validate_screen_key(screen_key: str) -> str:
    """Return a normalized screen identity or fail closed on invalid input."""
    if (
        not isinstance(screen_key, str)
        or len(screen_key) > _MAX_SCREEN_KEY_CHARS
        or not _SCREEN_KEY_PATTERN.fullmatch(screen_key)
    ):
        raise UiLocalizationValidationError(
            "ui_screen_key_invalid",
            "screen_key must be a dotted lowercase product identity up to 128 characters",
        )
    return screen_key


def validate_message_key(message_key: str) -> str:
    """Return a normalized message identity or fail closed on invalid input."""
    if (
        not isinstance(message_key, str)
        or len(message_key) > _MAX_MESSAGE_KEY_CHARS
        or not _MESSAGE_KEY_PATTERN.fullmatch(message_key)
    ):
        raise UiLocalizationValidationError(
            "ui_message_key_invalid",
            "message_key must be lowercase snake_case up to 128 characters",
        )
    return message_key


def _validate_translation_text(message_text: str) -> None:
    """Reject text that cannot cross the catalog's bounded UTF-8/PostgreSQL boundary."""
    if not isinstance(message_text, str):
        raise UiLocalizationValidationError(
            "ui_translation_input_invalid",
            "translated message must be a string",
        )
    if len(message_text) > _MAX_TRANSLATION_MESSAGE_CHARS:
        raise UiLocalizationValidationError(
            "ui_translation_input_invalid",
            "translated message exceeds the 16384-character product limit",
        )
    if "\x00" in message_text or any(
        0xD800 <= ord(character) <= 0xDFFF for character in message_text
    ):
        raise UiLocalizationValidationError(
            "ui_translation_input_invalid",
            "translated message must contain persistable Unicode scalar text without NUL",
        )


def _reject_placeholder_operators(message_text: str) -> None:
    """Reject formatter operators that Formatter.parse normalizes away when empty."""
    index = 0
    while index < len(message_text):
        character = message_text[index]
        if character == "{":
            if index + 1 < len(message_text) and message_text[index + 1] == "{":
                index += 2
                continue
            closing_index = message_text.find("}", index + 1)
            if closing_index == -1:
                return
            field_source = message_text[index + 1 : closing_index]
            if ":" in field_source or "!" in field_source:
                raise UiLocalizationValidationError(
                    "ui_placeholder_schema_invalid",
                    "placeholders must be simple named fields without conversion or format specifiers",
                )
            index = closing_index + 1
            continue
        if character == "}" and index + 1 < len(message_text) and message_text[index + 1] == "}":
            index += 2
            continue
        index += 1


def extract_placeholder_names(message_text: str) -> tuple[str, ...]:
    """Extract bounded simple named interpolation fields without evaluating the message."""
    _validate_translation_text(message_text)
    _reject_placeholder_operators(message_text)
    names: list[str] = []
    seen: set[str] = set()
    try:
        parsed = Formatter().parse(message_text)
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if (
                len(field_name) > _MAX_PLACEHOLDER_NAME_CHARS
                or not _PLACEHOLDER_NAME_PATTERN.fullmatch(field_name)
                or format_spec
                or conversion is not None
            ):
                raise UiLocalizationValidationError(
                    "ui_placeholder_schema_invalid",
                    "placeholders must be bounded simple named fields without conversion or format specifiers",
                )
            if field_name not in seen:
                if len(names) >= _MAX_PLACEHOLDER_SCHEMA_ITEMS:
                    raise UiLocalizationValidationError(
                        "ui_placeholder_schema_invalid",
                        "translated message contains too many unique placeholders",
                    )
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
    """Require translated text to preserve one bounded versioned placeholder schema."""
    if not isinstance(placeholder_schema, (tuple, list)):
        raise UiLocalizationValidationError(
            "ui_placeholder_schema_invalid",
            "placeholder schema must be a tuple or list of names",
        )
    if len(placeholder_schema) > _MAX_PLACEHOLDER_SCHEMA_ITEMS:
        raise UiLocalizationValidationError(
            "ui_placeholder_schema_invalid",
            "placeholder schema exceeds the 32-name product limit",
        )
    schema = tuple(placeholder_schema)
    if any(
        not isinstance(name, str)
        or len(name) > _MAX_PLACEHOLDER_NAME_CHARS
        or not _PLACEHOLDER_NAME_PATTERN.fullmatch(name)
        for name in schema
    ) or len(schema) != len(set(schema)):
        raise UiLocalizationValidationError(
            "ui_placeholder_schema_invalid",
            "placeholder schema must contain unique lowercase snake_case names up to 64 characters",
        )
    actual = extract_placeholder_names(translated_message)
    if set(actual) != set(schema):
        raise UiLocalizationValidationError(
            "ui_translation_placeholder_mismatch",
            "translated message placeholders do not match the versioned schema",
        )
    return actual
